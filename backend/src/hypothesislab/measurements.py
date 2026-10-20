"""Import real CSV data, require explicit units and fit a simple deterministic line."""
from __future__ import annotations
import csv
import io
import math
import warnings
from scipy.stats import linregress
from .validation import InputError

def _parse_csv(data: str, x_column: str, y_column: str) -> tuple[list[float], list[float], int]:
    """Parse a bounded, unambiguous CSV view without rewriting source bytes."""
    if not isinstance(data, str):
        raise InputError("CSV must be text")
    if data.startswith("\ufeff"):
        data = data[1:]
    if "\x00" in data:
        raise InputError("CSV contains an embedded NUL")
    try:
        reader = csv.reader(io.StringIO(data, newline=""), strict=True)
        headers = next(reader)
    except StopIteration as exc:
        raise InputError("CSV header is missing") from exc
    except csv.Error as exc:
        raise InputError("Malformed CSV header") from exc
    if not headers or any(not h or not h.strip() or h != h.strip() for h in headers):
        raise InputError("CSV headings must be nonempty and free of outer whitespace")
    if len(headers) != len(set(header.casefold() for header in headers)):
        raise InputError("Duplicate CSV headings are ambiguous")
    if x_column == y_column or x_column not in headers or y_column not in headers:
        raise InputError("CSV needs two different explicitly named measurement columns")
    x_index, y_index = headers.index(x_column), headers.index(y_column)
    xs, ys = [], []
    try:
        for row in reader:
            if len(xs) >= 10_000:
                raise InputError("Initial CSV importer supports at most 10,000 rows")
            if len(row) != len(headers):
                raise InputError(f"CSV row ending at line {reader.line_num} has {len(row)} fields; expected {len(headers)}")
            try:
                x, y = float(row[x_index]), float(row[y_index])
            except (TypeError, ValueError) as exc:
                raise InputError(f"Non-numeric/missing measurement on CSV line {reader.line_num}") from exc
            if not (math.isfinite(x) and math.isfinite(y)):
                raise InputError(f"Non-finite measurement on CSV line {reader.line_num}")
            xs.append(x)
            ys.append(y)
    except csv.Error as exc:
        raise InputError("Malformed CSV record") from exc
    if len(xs) < 3 or len(set(xs)) < 2:
        raise InputError('At least 3 records with 2 distinct x values required')
    return xs, ys, len(headers)


def validate_csv_structure(csv: str, x_column: str, y_column: str) -> tuple[list[float], list[float]]:
    """Preflight the bounded, finite CSV view before creating an approval ticket."""
    xs, ys, _ = _parse_csv(csv, x_column, y_column)
    return xs, ys


def fit_csv(csv: str, x_column: str, y_column: str, x_unit: str, y_unit: str) -> tuple[dict, bytes]:
    # Load plotting only when requested; building its font cache must not delay app launch.
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_svg import FigureCanvasSVG
    xs, ys, column_count = _parse_csv(csv, x_column, y_column)
    with warnings.catch_warnings():
        warnings.filterwarnings("error", category=RuntimeWarning)
        try:
            fit = linregress(xs, ys)
        except (RuntimeWarning, OverflowError, ValueError) as exc:
            raise InputError("Measurement range is numerically unstable for unscaled linear regression") from exc
    if not all(math.isfinite(float(value)) for value in
               (fit.slope, fit.intercept, fit.rvalue, fit.pvalue,
                fit.stderr, fit.intercept_stderr)):
        raise InputError("Regression produced non-finite values; inspect measurement scale and data quality")
    result={
        'input_rows':len(xs),'dropped_rows':0,'input_columns':column_count,
        'model':'ordinary unweighted simple linear regression (SciPy linregress)',
        'x_column':x_column,'y_column':y_column,'x_unit':x_unit,'y_unit':y_unit,
        'slope':float(fit.slope),'intercept':float(fit.intercept),
        'r_squared':float(fit.rvalue**2),'pvalue':float(fit.pvalue),
        'slope_standard_error':float(fit.stderr),
        'intercept_standard_error':float(fit.intercept_stderr),
        'assumptions':'Unweighted independent errors; not a general nonlinear kinetics inference',
        'source_type':'user-supplied observed CSV; values are not predicted/verified physical observations'
    }
    fig=Figure(figsize=(7,4.5),dpi=100)
    ax=fig.add_subplot(111)
    ax.scatter(xs,ys,label='Input measurements')
    ends=[min(xs),max(xs)]
    ax.plot(ends,[fit.intercept+fit.slope*x for x in ends],label='Least-squares fit')
    ax.set_xlabel(f'{x_column} ({x_unit})');ax.set_ylabel(f'{y_column} ({y_unit})')
    ax.legend();fig.tight_layout()
    canvas=FigureCanvasSVG(fig)
    output=io.BytesIO();canvas.print_svg(output)
    return result, output.getvalue()
