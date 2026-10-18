/**
 * Parse selected, explicitly printed facts from an ORCA output file.
 * This is deliberately a static reader: it never interprets input as commands
 * and does not infer a calculation method or chemistry result.
 */
const NUMBER = '[-+]?(?:\\d+(?:\\.\\d*)?|\\.\\d+)(?:[EeDd][-+]?\\d+)?';
const numberPattern = new RegExp(`^${NUMBER}$`);

function finiteNumber(value) {
  const source = String(value).trim();
  if (!numberPattern.test(source)) return null;
  const parsed = Number(source.replace(/[dD]/g, 'E'));
  return Number.isFinite(parsed) ? parsed : null;
}

function valueAt(value, line, unit) {
  return unit === undefined ? { value, line } : { value, line, unit };
}

function pushCheck(checks, severity, title, detail, line = null) {
  if (!checks.some((check) => check.title === title && check.line === line)) {
    checks.push({ severity, title, detail, line });
  }
}

function lastMatch(lines, expression, transform) {
  let match = null;
  lines.forEach((text, index) => {
    const found = text.match(expression);
    if (found) match = transform(found, index + 1);
  });
  return match;
}

function extractGeometry(lines, checks) {
  let finalGeometry = null;
  let incompleteHeader = null;

  for (let index = 0; index < lines.length; index += 1) {
    if (!/CARTESIAN\s+COORDINATES\s*\(\s*ANGSTRO(?:E|Ö)?M\s*\)/i.test(lines[index])) continue;
    const atoms = [];
    let sawContent = false;
    let ended = false;
    let malformed = false;

    for (let cursor = index + 1; cursor < lines.length; cursor += 1) {
      const text = lines[cursor];
      if (/CARTESIAN\s+COORDINATES|VIBRATIONAL\s+FREQUENCIES|FINAL\s+SINGLE\s+POINT\s+ENERGY/i.test(text)) {
        ended = true;
        break;
      }
      const atom = text.match(new RegExp(`^\\s*([A-Z][a-z]?)\\s+(${NUMBER})\\s+(${NUMBER})\\s+(${NUMBER})\\s*$`));
      if (atom) {
        const coordinates = atom.slice(2).map(finiteNumber);
        if (coordinates.every((coordinate) => coordinate !== null)) {
          atoms.push({ element: atom[1], x: coordinates[0], y: coordinates[1], z: coordinates[2] });
          sawContent = true;
          continue;
        }
        malformed = true;
        break;
      }
      if (/^\s*-{3,}\s*$/.test(text)) {
        continue;
      }
      if (/^\s*$/.test(text)) {
        if (atoms.length > 0 && sawContent) {
          // A newline at physical EOF is not evidence that ORCA finished a
          // coordinate table; require later content after the blank boundary.
          ended = lines.slice(cursor + 1).some((remaining) => /\S/.test(remaining));
          break;
        }
        continue;
      }
      if (atoms.length > 0) {
        // Atom-like text after a coordinate row is a malformed row, not a
        // valid table boundary. Do not silently accept its valid prefix.
        malformed = /^\s*[A-Z][a-z]?\b/.test(text);
        ended = !malformed;
        break;
      }
      if (/\S/.test(text)) sawContent = true;
    }

    if (atoms.length > 0 && ended && !malformed) {
      finalGeometry = { atoms, line: index + 1, unit: 'Å' };
      incompleteHeader = null;
    } else {
      incompleteHeader = index + 1;
    }
  }

  if (incompleteHeader !== null) {
    const retained = finalGeometry === null
      ? 'No complete coordinate block followed.'
      : 'An earlier complete coordinate block was retained.';
    pushCheck(checks, 'warning', 'Incomplete Cartesian coordinates', `The last detected ANGSTROEM coordinate block was incomplete or malformed. ${retained}`, incompleteHeader);
  }
  return finalGeometry;
}

function extractFrequencies(lines) {
  let finalSection = null;
  for (let index = 0; index < lines.length; index += 1) {
    if (!/VIBRATIONAL\s+FREQUENCIES/i.test(lines[index])) continue;
    const frequencies = [];
    for (let cursor = index + 1; cursor < lines.length; cursor += 1) {
      const text = lines[cursor];
      if (/^(?:\s*(?:IR\s+SPECTRUM|RAMAN\s+SPECTRUM|THERMOCHEMISTRY|CARTESIAN\s+COORDINATES|NORMAL\s+MODES))/i.test(text)) break;
      const row = text.match(new RegExp(String.raw`^\s*(\d+)\s*:\s*(${NUMBER})\s*(?:cm(?:\*\*)?-?1|cm\^-?1)`, 'i'));
      if (row) {
        const frequency = finiteNumber(row[2]);
        if (frequency !== null) frequencies.push({ mode: Number(row[1]), value: frequency, line: cursor + 1 });
      }
    }
    if (frequencies.length > 0) finalSection = frequencies;
  }
  return finalSection || [];
}

/**
 * @param {string} text ORCA output text.
 * @param {string} filename Source label only; it is not opened or executed.
 */
export function parseOrca(text, filename = 'calculation.out') {
  const lines = String(text ?? '').replace(/^\uFEFF/, '').split(/\r?\n/);
  const checks = [];
  const versionBannerLines = lines.reduce((found, line, index) => (
    /\bPROGRAM\s+VERSION\b/i.test(line) ? found.concat(index + 1) : found
  ), []);
  const logoLines = lines.reduce((found, line, index) => (
    /\*\s*O\s+R\s+C\s+A\s*\*/i.test(line) ? found.concat(index + 1) : found
  ), []);
  const normalLines = lines.reduce((found, line, index) => (/ORCA\s+TERMINATED\s+NORMALLY/i.test(line) ? found.concat(index + 1) : found), []);
  const finalEnergyLines = lines.reduce((found, line, index) => (/FINAL\s+SINGLE\s+POINT\s+ENERGY/i.test(line) ? found.concat(index + 1) : found), []);
  const otherTokens = lines.filter((line) => /\b(?:ORCA|SCF|CARTESIAN\s+COORDINATES|VIBRATIONAL\s+FREQUENCIES)\b/i.test(line)).length;
  const recognized = versionBannerLines.length > 0 || logoLines.length > 0 || normalLines.length > 0 || (finalEnergyLines.length > 0 && otherTokens > 1);

  const result = {
    filename,
    recognized,
    lines,
    version: lastMatch(lines, /\bPROGRAM\s+VERSION\s+([^\s,;]+)/i, (match, line) => valueAt(match[1], line)),
    keywords: [],
    charge: lastMatch(lines, /(?:TOTAL\s+)?CHARGE(?:\s+CHARGE)?\s*(?:[:=]|\.{2,})\s*([-+]?\d+)/i, (match, line) => valueAt(Number(match[1]), line)),
    multiplicity: lastMatch(lines, /MULTIPLICITY(?:\s+MULT)?\s*(?:[:=]|\.{2,})\s*(\d+)/i, (match, line) => valueAt(Number(match[1]), line)),
    energy: null,
    energies: [],
    geometry: null,
    frequencies: [],
    thermochemistry: { temperature: null, zpe: null, enthalpy: null, gibbs: null },
    termination: 'unknown',
    terminationLine: null,
    optimization: 'unknown',
    optimizationLine: null,
    scf: 'unknown',
    scfLine: null,
    multiJob: false,
    checks,
  };

  lines.forEach((line, index) => {
    const lineNumber = index + 1;
    const keyword = line.match(/^\s*\|\s*\d+>\s*!\s*(.+?)\s*$/)
      || line.match(/^\s*!\s*(?!.*!\s*$)(.+?)\s*$/);
    if (keyword) result.keywords.push(valueAt(keyword[1], lineNumber));

    const energy = line.match(new RegExp(`FINAL\\s+SINGLE\\s+POINT\\s+ENERGY\\s+(${NUMBER})`, 'i'));
    if (energy) {
      const value = finiteNumber(energy[1]);
      if (value !== null) {
        const evidence = valueAt(value, lineNumber, 'Eh');
        result.energies.push(evidence);
        result.energy = evidence;
      }
    }

    if (/ORCA\s+TERMINATED\s+NORMALLY/i.test(line)) {
      result.termination = 'normal';
      result.terminationLine = lineNumber;
    }
    if (/(?:ORCA\s+(?:FINISHED|TERMINATED).{0,40}(?:ERROR|ABNORM)|ERROR\s+TERMINATION|ORCA\s+ERROR)/i.test(line)) {
      result.termination = 'error';
      result.terminationLine = lineNumber;
    }

    if (/(?:OPTIMIZATION\s+(?:HAS\s+)?(?:CONVERGED|CONVERGENCE\s+ACHIEVED)|THE\s+OPTIMIZATION\s+HAS\s+CONVERGED)/i.test(line)) {
      result.optimization = 'converged';
      result.optimizationLine = lineNumber;
    } else if (/(?:OPTIMIZATION\s+(?:HAS\s+)?NOT\s+CONVERGED|OPTIMIZATION\s+(?:DID\s+NOT|FAILED\s+TO)\s+CONVERGE)/i.test(line)) {
      result.optimization = 'not_converged';
      result.optimizationLine = lineNumber;
    } else if (/\*\s*GEOMETRY\s+OPTIMIZATION\s+RUN\s*\*/i.test(line)) {
      result.optimizationLine = lineNumber;
    }

    if (/SCF\s+(?:CONVERGED|ITERATIONS?\s+CONVERGED)/i.test(line)) {
      result.scf = 'converged';
      result.scfLine = lineNumber;
    } else if (/(?:SCF\s+(?:NOT\s+CONVERGED|FAILED)|SCF\s+CONVERGENCE\s+FAILED)/i.test(line)) {
      result.scf = 'not_converged';
      result.scfLine = lineNumber;
    }
  });

  result.geometry = extractGeometry(lines, checks);
  result.frequencies = extractFrequencies(lines);
  result.thermochemistry.temperature = lastMatch(lines, new RegExp(String.raw`(?:THERMOCHEMICAL\s+)?TEMPERATURE[^\d+-]*(${NUMBER})\s*K\b`, 'i'), (match, line) => valueAt(finiteNumber(match[1]), line, 'K'));
  result.thermochemistry.zpe = lastMatch(lines, new RegExp(String.raw`(?:ZERO[ -]?POINT\s+ENERGY|ZPE)[^\d+-]*(${NUMBER})\s*(?:Eh|Hartree)`, 'i'), (match, line) => valueAt(finiteNumber(match[1]), line, 'Eh'));
  result.thermochemistry.enthalpy = lastMatch(lines, new RegExp(String.raw`(?:TOTAL\s+)?ENTHALPY[^\d+-]*(${NUMBER})\s*(?:Eh|Hartree)`, 'i'), (match, line) => valueAt(finiteNumber(match[1]), line, 'Eh'));
  result.thermochemistry.gibbs = lastMatch(lines, new RegExp(String.raw`(?:FINAL\s+)?GIBBS(?:\s+FREE)?\s+ENERGY[^\d+-]*(${NUMBER})\s*(?:Eh|Hartree)`, 'i'), (match, line) => valueAt(finiteNumber(match[1]), line, 'Eh'));

  if (result.optimization === 'unknown' && result.keywords.length > 0) {
    const requestedOptimization = result.keywords.some(({ value }) => /\b(?!(?:noopt|nooptimize)\b)[a-z]*opt[a-z]*\b/i.test(value));
    if (!requestedOptimization) result.optimization = 'not_requested';
  }

  const jobMarkers = lines.reduce((count, line) => count + (
    /^(?:\s*\|\s*\d+>\s*)?\s*\$new_job\b|^\s*COMPOUND\s+JOB\s+(?:MAINJOB|\d+)\b/i.test(line) ? 1 : 0
  ), 0);
  result.multiJob = versionBannerLines.length > 1 || jobMarkers > 0;
  if (result.multiJob) {
    pushCheck(checks, 'info', 'Multiple ORCA jobs detected', 'Reported scalar values are the last observed values; this parser does not prove that properties belong to one job.');
  }

  if (result.termination === 'error') {
    pushCheck(checks, 'warning', 'ORCA error termination', 'The last observed termination marker reports an error.', result.terminationLine);
  } else if (recognized && result.termination === 'unknown') {
    pushCheck(checks, 'warning', 'No explicit termination marker', 'The output may be truncated or ended before ORCA reported its termination.');
  }
  if (recognized && result.energy === null) {
    pushCheck(checks, 'warning', 'No final single-point energy', 'No finite FINAL SINGLE POINT ENERGY marker was found.');
  }
  if (recognized && result.geometry === null) {
    pushCheck(checks, 'warning', 'No final Cartesian geometry', 'No complete ANGSTROEM Cartesian-coordinate block was found.');
  }
  if (result.optimization === 'not_converged') {
    pushCheck(checks, 'warning', 'Geometry optimization did not converge', 'A non-convergence marker was found even if ORCA later terminated normally.', result.optimizationLine);
  }
  if (result.scf === 'not_converged') {
    pushCheck(checks, 'warning', 'SCF did not converge', 'An SCF non-convergence marker was found.');
  }

  return result;
}
