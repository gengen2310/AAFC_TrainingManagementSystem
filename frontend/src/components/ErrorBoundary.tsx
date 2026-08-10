import { Component, type ReactNode, type ErrorInfo } from "react";

interface Props { children: ReactNode; }
interface State { error: Error | null; }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[ErrorBoundary]", error.message, info.componentStack?.slice(0, 300));
  }

  render() {
    if (this.state.error) {
      return (
        <div className="errnote" role="alert" style={{ margin: "32px 24px" }}>
          <strong>Something went wrong on this page.</strong>
          <p style={{ marginTop: 8, fontSize: 13, color: "var(--muted-text, #6b7a87)" }}>
            If this keeps happening, contact support.
          </p>
          <button
            className="btn sm out"
            style={{ marginTop: 12 }}
            onClick={() => this.setState({ error: null })}
          >
            Reload page
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
