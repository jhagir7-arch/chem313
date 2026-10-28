import React from 'react';
import {createRoot} from 'react-dom/client';
import '../../design/tokens.css';
import './styles/shell.css';
import {App} from './App';
import {reportError} from './engine';

class ErrorBoundary extends React.Component<{children: React.ReactNode}, {error: Error | null}> {
  state = {error: null as Error | null};
  static getDerivedStateFromError(error: Error) { return {error}; }
  componentDidCatch(error: Error, info: React.ErrorInfo) { reportError('error', `${error.stack ?? error.message}\n${info.componentStack ?? ''}`); }
  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="err-box" role="alert">
        <strong>Chem313 hit an error in the interface.</strong>
        <pre className="mono" style={{whiteSpace: 'pre-wrap', margin: '8px 0 0'}}>{this.state.error.stack ?? String(this.state.error)}</pre>
        <button type="button" className="tool" style={{marginTop: 8}} onClick={() => this.setState({error: null})}>Try again</button>
      </div>
    );
  }
}

window.addEventListener('error', (e) => reportError('error', `${e.message} @ ${e.filename}:${e.lineno}`));
window.addEventListener('unhandledrejection', (e) => reportError('error', `unhandled rejection: ${String((e as PromiseRejectionEvent).reason?.stack ?? (e as PromiseRejectionEvent).reason)}`));

createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>,
);
