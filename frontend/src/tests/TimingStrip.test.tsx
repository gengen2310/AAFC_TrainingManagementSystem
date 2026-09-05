import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { TimingStrip } from '../components/planning/TimingStrip';

const blocks = [
  { label: 'Opening Parade', start_time: '18:00', end_time: '18:20', is_instructional: false, display_order: 0 },
  { label: 'Period 1', start_time: '18:30', end_time: '19:10', is_instructional: true, display_order: 1 },
  { label: 'Break', start_time: '19:10', end_time: '19:20', is_instructional: false, display_order: 2 },
  { label: 'Period 2', start_time: '19:20', end_time: '20:00', is_instructional: true, display_order: 3 },
];

const periods = [
  { period_number: 1, label: 'Period 1', start_time: '18:30', end_time: '19:10' },
  { period_number: 2, label: 'Period 2', start_time: '19:20', end_time: '20:00' },
];

describe('TimingStrip', () => {
  it('renders all blocks', () => {
    render(<TimingStrip blocks={blocks} periods={periods} />);
    expect(screen.getByText('Opening Parade')).toBeTruthy();
    expect(screen.getByText('Period 1')).toBeTruthy();
    expect(screen.getByText('Break')).toBeTruthy();
    expect(screen.getByText('Period 2')).toBeTruthy();
  });

  it('applies data-instructional attribute for styling', () => {
    const { container } = render(<TimingStrip blocks={blocks} periods={periods} />);
    const pills = container.querySelectorAll('[data-instructional]');
    expect(pills.length).toBeGreaterThan(0);
  });

  it('renders gracefully with empty blocks', () => {
    const { container } = render(<TimingStrip blocks={[]} periods={[]} />);
    expect(container.firstChild).toBeTruthy();
  });

  it('shows time ranges on blocks that have times', () => {
    render(<TimingStrip blocks={blocks} periods={periods} />);
    expect(screen.getByText('18:00–18:20')).toBeTruthy();
  });

  it('falls back to period labels when blocks is empty', () => {
    render(<TimingStrip blocks={[]} periods={periods} />);
    expect(screen.getAllByText(/Period/).length).toBeGreaterThan(0);
  });
});
