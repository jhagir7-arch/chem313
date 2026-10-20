export type Section='learn'|'molecule'|'calculate'|'records'|'labs';
export const SECTIONS: readonly {id:Section;label:string;workspace:string;icon:string;hint:string}[];
export const CORE_WORKSPACES: readonly string[];
export function sectionForWorkspace(id:string):Section;
export function visibleWorkspaces<T extends {id:string}>(tabs:T[], labs:boolean):T[];
export function workspaceNeedsLabs(id:string):boolean;
