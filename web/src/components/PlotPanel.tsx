import { useMemo } from 'react';
import Plot from 'react-plotly.js';
import { useAnalysisStore } from '../stores/analysisStore';

export function PlotPanel() {
  const curves = useAnalysisStore((s) => s.curves);
  const isLogScale = useAnalysisStore((s) => s.isLogScale);
  const selectedType = useAnalysisStore((s) => s.selectedType);

  const data = useMemo(
    () =>
      curves
        .filter((c) => c.visible)
        .map((c) => ({
          x: c.x,
          y: c.y,
          type: 'scatter' as const,
          mode: 'lines+markers' as const,
          name: c.name,
          line: { color: c.color, width: 2 },
          marker: { size: 4 },
        })),
    [curves]
  );

  const layout = useMemo(
    () => ({
      xaxis: {
        title: selectedType === 'output' ? 'Vds (V)' : 'Vgs (V)',
        gridcolor: '#e0e0e0',
        zeroline: true,
      },
      yaxis: {
        title: 'Drain Current Id (A)',
        type: (isLogScale ? 'log' : 'linear') as 'log' | 'linear',
        gridcolor: '#e0e0e0',
        zeroline: true,
      },
      legend: { x: 1.02, y: 1 },
      margin: { l: 70, r: 20, t: 20, b: 60 },
      showlegend: true,
    }),
    [isLogScale, selectedType]
  );

  return (
    <div style={{ width: '100%', height: '100%', minHeight: 400 }}>
      <Plot
        data={data}
        layout={layout}
        style={{ width: '100%', height: '100%' }}
        useResizeHandler
        config={{ responsive: true, displaylogo: false }}
      />
    </div>
  );
}
