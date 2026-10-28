// All engine traffic goes through the Rust host (`engine_request`): the webview never sees
// the loopback port or the session token, and no CORS allowance is needed.
import {invoke} from '@tauri-apps/api/core';
import {listen, type UnlistenFn} from '@tauri-apps/api/event';

export type EngineStatus = {ready: boolean; url: string | null; error: string | null; data_dir: string};

type Proxied = {status: number; body: string};

export async function engineStatus(): Promise<EngineStatus> {
  return invoke<EngineStatus>('engine_status');
}

async function proxied(method: 'GET' | 'POST', path: string, body?: unknown): Promise<Proxied> {
  return invoke<Proxied>('engine_request', {method, path, body: body === undefined ? null : JSON.stringify(body)});
}

function failure(reply: Proxied, parsed: any): Error {
  const detail = parsed && typeof parsed.detail === 'string' ? parsed.detail : `Engine request failed (${reply.status})`;
  return new Error(detail);
}

export async function request<T = unknown>(path: string, body?: unknown): Promise<T> {
  const reply = await proxied(body === undefined ? 'GET' : 'POST', path, body);
  let parsed: any = null;
  try {
    parsed = reply.body ? JSON.parse(reply.body) : null;
  } catch {
    parsed = null;
  }
  if (reply.status < 200 || reply.status >= 300) throw failure(reply, parsed);
  return parsed as T;
}

/** A saved artefact's raw text (SDF, JSON, SVG); integrity is checked by the engine against its event log. */
export async function artifactText(relativePath: string): Promise<string> {
  const [project, group, file] = relativePath.split('/');
  const reply = await proxied('GET', `/api/projects/${encodeURIComponent(project)}/artifact/${group}/${file}`);
  if (reply.status < 200 || reply.status >= 300) throw failure(reply, null);
  return reply.body;
}

export type Artifact = {relative_path: string; sha256: string; bytes: number};
export type Reply<R = any> = {status: string; action: string; result: R; artifacts: Artifact[]; warning?: string};

/** Project-writing actions are two-step: the engine issues a single-use approval token on preview,
 *  and execute must present it. Read-only actions get no token and go straight through. */
export async function execute<R = any>(action: string, params: Record<string, unknown>, project = 'default') {
  const preview = await request<{preview_token?: string | null}>('/api/preview', {action, params, project});
  const body: Record<string, unknown> = {action, params, project, approved: true};
  if (preview.preview_token) body.preview_token = preview.preview_token;
  return request<Reply<R>>('/api/execute', body);
}

// ---- Catalog: what the engine offers. The interface shows nothing it does not read here. ----

export type CatalogMolecule = {id: string; name: string; smiles: string; formula: string};
export type ForceField = {id: string; label: string; note: string; elements: string[]};
export type Catalog = {
  schema: string;
  molecules: CatalogMolecule[];
  relaxation: {
    action: string;
    embedding: string;
    defaults: {force_field: string; seed: number; max_iterations: number};
    limits: {seed: {min: number; max: number}; max_iterations: {min: number; max: number}; heavy_atoms: {max: number}; force_tolerance: number; energy_tolerance: number};
    inputs: string[];
    force_fields: ForceField[];
    scope: string;
  };
};

export const catalog = () => request<Catalog>('/api/catalog');

// ---- Persisted calculations: the engine's append-only event log is the source of truth. ----

export type EventRecord = {
  version: number; timestamp_utc: string; project: string; action: string; parameters_sha256: string;
  artifacts: Artifact[]; result: Record<string, any>;
};

export const events = (project = 'default') => request<{project: string; events: EventRecord[]}>(`/api/projects/${encodeURIComponent(project)}/events`);

export function onMenu(handler: (id: string) => void): Promise<UnlistenFn> {
  return listen<string>('menu', (event) => handler(event.payload));
}

/** Ask the host to save text through a native dialog; resolves to the path or null when cancelled. */
export function saveTextFile(suggestedName: string, contents: string): Promise<string | null> {
  return invoke<string | null>('save_text_file', {suggestedName, contents});
}

/** Ask the host to open a structure file (.mol/.sdf) through a native dialog; resolves to its text or null. */
export function openStructureFile(): Promise<{name: string; contents: string} | null> {
  return invoke<{name: string; contents: string} | null>('open_structure_file');
}

/** Forward an interface error to the host log; never throws. */
export function reportError(level: 'error' | 'warn', message: string): void {
  invoke('log_message', {level, message}).catch(() => undefined);
}
