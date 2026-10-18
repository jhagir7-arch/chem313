//! Small host adapter: forwards explicit CLI tokens, does not interpret chemistry or execute arbitrary code.
use std::env;
use std::process::{Command, ExitCode};

fn python_command() -> String {
    env::var("HYPOTHESISLAB_PYTHON").unwrap_or_else(|_| "python3".to_string())
}
fn main() -> ExitCode {
    let args: Vec<String> = env::args().skip(1).collect();
    if args.is_empty() {
        eprintln!("usage: hypothesislab-bridge [--root DATA] [--project ID] preview|apply|verify|events ACTION [--smiles TEXT|--molfile-path FILE]");
        return ExitCode::from(2);
    }
    let status = Command::new(python_command()).arg("-m").arg("hypothesislab").args(args).status();
    match status {
        Ok(s) => ExitCode::from(s.code().unwrap_or(1).clamp(0, 255) as u8),
        Err(error) => { eprintln!("Unable to start the installed HypothesisLab Python engine: {error}"); ExitCode::from(1) }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test] fn python_default_is_nonblank() { assert!(!python_command().is_empty()); }
}
