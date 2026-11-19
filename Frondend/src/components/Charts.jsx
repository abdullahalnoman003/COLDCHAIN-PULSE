import { useMemo } from 'react';
import { parseApiDate } from '../lib/api';

export function ShipmentChart({ summary }) {
  const entries = [
    ['In transit', summary?.shipments_by_status?.in_transit || 0, '#3978f6'],
    ['Delivered', summary?.shipments_by_status?.delivered || 0, '#20a879'],
    ['Created', summary?.shipments_by_status?.created || 0, '#8c9aaf'],
    ['Cancelled', summary?.shipments_by_status?.cancelled || 0, '#d7deea'],
  ];
  const total = entries.reduce((sum, row) => sum + row[1], 0);
  let offset = 0;
  const arcs = entries.map(([label, value, color]) => {
    const start = offset; const ratio = total ? value / total : 0; offset += ratio;
    return { label, value, color, dash: `${ratio * 251.2} ${251.2}`, offset: -start * 251.2 };
  });
  return <div className="shipment-chart">
    <div className="donut-wrap"><svg viewBox="0 0 100 100" role="img" aria-label={`${total} total shipments by status`}>
      <circle cx="50" cy="50" r="40" fill="none" stroke="#edf1f7" strokeWidth="13" />
      {arcs.map((arc) => <circle key={arc.label} cx="50" cy="50" r="40" fill="none" stroke={arc.color} strokeWidth="13" strokeDasharray={arc.dash} strokeDashoffset={arc.offset} transform="rotate(-90 50 50)" strokeLinecap="butt" />)}
    </svg><div className="donut-center"><strong>{total.toLocaleString()}</strong><span>Total</span></div></div>
    <div className="chart-legend">{entries.map(([label, value, color]) => <div key={label}><span className="legend-name"><i style={{ background: color }} />{label}</span><strong>{Number(value).toLocaleString()}</strong></div>)}</div>
  </div>;
}

export function TemperatureChart({ readings, shipment }) {
  const points = useMemo(() => readings.map((reading, index) => ({ ...reading, index })), [readings]);
  if (!points.length) return <div className="chart-empty">Temperature history will appear when sensor readings are available.</div>;
  const values = points.map((point) => Number(point.temperature));
  const min = Math.min(...values, Number(shipment?.min_temp ?? 2));
  const max = Math.max(...values, Number(shipment?.max_temp ?? 8));
  const span = Math.max(max - min, 2);
  const low = min - span * 0.2; const high = max + span * 0.2;
  const width = 620; const height = 176; const pad = { x: 18, y: 20 };
  const coords = points.map((point, i) => ({ x: pad.x + (i / Math.max(points.length - 1, 1)) * (width - pad.x * 2), y: pad.y + ((high - Number(point.temperature)) / (high - low)) * (height - pad.y * 2) }));
  const path = coords.map((p, i) => `${i ? 'L' : 'M'} ${p.x} ${p.y}`).join(' ');
  const minTemp = Number(shipment?.min_temp ?? 2); const maxTemp = Number(shipment?.max_temp ?? 8);
  const yFor = (value) => pad.y + ((high - value) / (high - low)) * (height - pad.y * 2);
  const last = points[points.length - 1];
  return <div className="temp-chart-wrap"><div className="temp-chart-head"><div><strong>{Number(last.temperature).toFixed(1)}°C</strong><span>Latest reading</span></div><div className="range-note"><span>Safe range</span><b>{minTemp}° to {maxTemp}°C</b></div></div>
    <svg className="temp-chart" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" role="img" aria-label="Temperature readings over time">
      <rect x={pad.x} y={yFor(maxTemp)} width={width - pad.x * 2} height={Math.max(0, yFor(minTemp) - yFor(maxTemp))} rx="5" fill="#e8f7f1" />
      {[0, 1, 2, 3].map((line) => { const y = pad.y + line * (height - pad.y * 2) / 3; return <line key={line} x1={pad.x} x2={width - pad.x} y1={y} y2={y} stroke="#edf1f7" strokeDasharray="4 5" />; })}
      <path d={path} fill="none" stroke="#3978f6" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      {coords.map((point, i) => i === coords.length - 1 ? <circle key={i} cx={point.x} cy={point.y} r="5" fill="#3978f6" stroke="white" strokeWidth="3" /> : null)}
    </svg><div className="chart-times"><span>{parseApiDate(points[0].recorded_at)?.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span><span>{parseApiDate(last.recorded_at)?.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span></div>
  </div>;
}
