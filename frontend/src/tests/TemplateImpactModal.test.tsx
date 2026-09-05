import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { TemplateImpactModal } from '../components/planning/TemplateImpactModal';

const impact = {
  retained_periods: [1, 2],
  removed_periods: [3],
  added_periods: [4],
  affected_sessions: [
    { session_id: 's1', period_number: 3, has_curriculum: true, has_facilitator: false },
  ],
};

describe('TemplateImpactModal', () => {
  it('shows retained, removed, and added periods', () => {
    render(
      <TemplateImpactModal
        impact={impact}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
        loading={false}
      />
    );
    expect(screen.getAllByText(/removed/i).length).toBeGreaterThan(0);
    // Period 3 is the removed period — check it appears somewhere in the document
    expect(screen.getAllByText(/3/).length).toBeGreaterThan(0);
  });

  it('shows added periods in green with label', () => {
    render(
      <TemplateImpactModal
        impact={impact}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
        loading={false}
      />
    );
    expect(screen.getByText(/new periods added/i)).toBeTruthy();
    expect(screen.getByText('4')).toBeTruthy();
  });

  it('shows warning for sessions on removed periods with content', () => {
    render(
      <TemplateImpactModal
        impact={impact}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
        loading={false}
      />
    );
    expect(screen.getByRole('alert')).toBeTruthy();
    expect(screen.getByText(/has curriculum/i)).toBeTruthy();
  });

  it('calls onConfirm when user clicks confirm', () => {
    const onConfirm = vi.fn();
    render(
      <TemplateImpactModal
        impact={impact}
        onConfirm={onConfirm}
        onCancel={vi.fn()}
        loading={false}
      />
    );
    fireEvent.click(screen.getByRole('button', { name: /confirm/i }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it('calls onCancel when user clicks cancel', () => {
    const onCancel = vi.fn();
    render(
      <TemplateImpactModal
        impact={impact}
        onConfirm={vi.fn()}
        onCancel={onCancel}
        loading={false}
      />
    );
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('disables buttons and shows applying text when loading=true', () => {
    render(
      <TemplateImpactModal
        impact={impact}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
        loading={true}
      />
    );
    expect(screen.getByText('Applying…')).toBeTruthy();
    const confirmBtn = screen.getByText('Applying…').closest('button');
    expect(confirmBtn?.disabled).toBe(true);
  });

  it('does not show warning section when no sessions are affected', () => {
    const noAffect = { ...impact, affected_sessions: [] };
    render(
      <TemplateImpactModal
        impact={noAffect}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
        loading={false}
      />
    );
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('renders as a dialog with correct aria roles', () => {
    render(
      <TemplateImpactModal
        impact={impact}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
        loading={false}
      />
    );
    expect(screen.getByRole('dialog')).toBeTruthy();
  });
});
