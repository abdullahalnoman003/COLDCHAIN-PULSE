const LABELS = { in_transit: 'In transit', delivered: 'Delivered', created: 'Created', cancelled: 'Cancelled', ok: 'Safe', warning: 'Warning', critical: 'Critical' };
export function StatusBadge({ value, type = 'status' }) {
  const tone = type === 'temperature' ? (value === 'ok' ? 'safe' : value) : value;
  return <span className={`badge badge-${tone}`}><i />{LABELS[value] || value?.replaceAll('_', ' ') || 'Unknown'}</span>;
}
