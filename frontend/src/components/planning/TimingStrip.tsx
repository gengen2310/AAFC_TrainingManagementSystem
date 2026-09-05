// DESIGN: Task 9 will apply additional visual polish (frontend-design + apple-design skills).
import type { TimingStripEntry, InstructionalPeriod } from '../../api/types';
import styles from './TimingStrip.module.css';

interface Props {
  blocks: TimingStripEntry[];
  /** Instructional periods from the night snapshot, in period_number order. */
  periods: InstructionalPeriod[];
}

function formatTimeRange(start: string | null, end: string | null): string {
  if (!start && !end) return '';
  if (start && end) return `${start}–${end}`;
  return start ?? end ?? '';
}

export function TimingStrip({ blocks, periods }: Props) {
  if (blocks.length === 0 && periods.length === 0) {
    return <div className={styles.strip} aria-hidden="true" />;
  }

  // Fallback: if no strip data, synthesise from periods only
  const displayBlocks = blocks.length > 0
    ? blocks
    : periods.map((p, i): TimingStripEntry => ({
        label: p.label,
        start_time: p.start_time,
        end_time: p.end_time,
        is_instructional: true,
        display_order: i,
      }));

  return (
    <div
      className={styles.strip}
      role="list"
      aria-label="Parade night timing"
    >
      {displayBlocks.map((block, idx) => (
        <div
          key={idx}
          className={styles.block}
          data-instructional={block.is_instructional ? 'true' : 'false'}
          role="listitem"
          title={formatTimeRange(block.start_time, block.end_time) || block.label}
        >
          <span className={styles.blockLabel}>{block.label}</span>
          {(block.start_time || block.end_time) && (
            <span className={styles.blockTime}>
              {formatTimeRange(block.start_time, block.end_time)}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
