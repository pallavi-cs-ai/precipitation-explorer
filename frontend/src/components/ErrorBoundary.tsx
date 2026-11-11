import { Component, type ReactNode } from 'react'
import { Button } from './ui/button'
export class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() {
    return { failed: true }
  }
  render() {
    return this.state.failed ? (
      <main className="fatal">
        <h1>The explorer needs a fresh start.</h1>
        <p>An unexpected display error occurred. Your forecast data has not been changed.</p>
        <Button onClick={() => window.location.reload()}>Reload explorer</Button>
      </main>
    ) : (
      this.props.children
    )
  }
}
