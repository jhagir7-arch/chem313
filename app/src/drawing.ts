/** Draft structures belong to the molecule they were drawn from. */
export class DrawingStore {
  private drawings = new Map<string, string>();
  get(id: string): string | undefined { return this.drawings.get(id); }
  save(id: string, molblock: string): void { this.drawings.set(id, molblock); }
  async snapshot(id: string, read: () => Promise<string>): Promise<string> {
    const molblock = await read();
    // V2000 counts line carries the atom count; an empty editor still exports a molfile header.
    const lines = molblock.split(/\r?\n/);
    if (!molblock.trim() || (lines.length >= 4 && /^\s*0\s/.test(lines[3]))) throw new Error('The structure is empty');
    this.save(id, molblock);
    return molblock;
  }
}
