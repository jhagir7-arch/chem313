"""Frozen local service and bounded scientific worker entry points."""
import sys

if __name__ == "__main__":
    if sys.argv[1:] == ["--science-worker"]:
        from hypothesislab.science_worker import main
    else:
        from hypothesislab.desktop import main
    main()
