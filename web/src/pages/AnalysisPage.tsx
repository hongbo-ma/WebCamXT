import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button, Select, Spin, Radio, App, Checkbox, Tag, InputNumber } from 'antd';
import {
  ArrowLeftOutlined, LineChartOutlined, ThunderboltOutlined,
  DeleteOutlined, ScissorOutlined,
} from '@ant-design/icons';
import { useAnalysisStore } from '../stores/analysisStore';
import { PlotPanel } from '../components/PlotPanel';
import { SimulationDialog } from '../components/SimulationDialog';

export function AnalysisPage() {
  const { fileId } = useParams<{ fileId: string }>();
  const navigate = useNavigate();
  const { message } = App.useApp();
  const store = useAnalysisStore();

  const [simDialogOpen, setSimDialogOpen] = useState(false);
  const [plotting, setPlotting] = useState(false);
  const [fitting, setFitting] = useState(false);
  const [simType, setSimType] = useState<'output' | 'transfer'>('output');
  const [simW, setSimW] = useState(0);
  const [simL, setSimL] = useState(0);
  const [vgsStart, setVgsStart] = useState(0);
  const [vgsEnd, setVgsEnd] = useState(20);
  const [vdsStart, setVdsStart] = useState(0);
  const [vdsEnd, setVdsEnd] = useState(20);
  const [step, setStep] = useState(0.1);

  useEffect(() => {
    if (fileId) {
      store.loadFile(Number(fileId)).catch(() => {
        message.error('Failed to load file');
        navigate('/files');
      });
    }
  }, [fileId]);

  useEffect(() => {
    if (store.selectedW !== null) setSimW(store.selectedW);
    if (store.selectedL !== null) setSimL(store.selectedL);
  }, [store.selectedW, store.selectedL]);

  const handlePlot = async () => {
    setPlotting(true);
    try {
      await store.plot();
    } catch (err: any) {
      message.error(err.response?.data?.error || 'Plot failed');
    } finally {
      setPlotting(false);
    }
  };

  const handleAutoFitting = async () => {
    setFitting(true);
    try {
      await store.autoFitting({
        t_tail: 0.025, t_deep: 0.05, g_tail: 1.0, g_deep: 0.4,
        T: 300, mu_free: 0.8, Vfb: -0.8, phi_F0: 0.4, CoxArea: 0.03,
      });
    } catch (err: any) {
      message.error(err.response?.data?.error || 'Fitting failed');
    } finally {
      setFitting(false);
    }
  };

  const handleSimulate = async (physicsParams: any) => {
    const typeSel = simType === 'output' ? 0 : 1;
    await store.simulate({
      file_id: store.fileId!,
      w: simW, l: simL, type_sel: typeSel as 0 | 1,
      vgs_min: vgsStart, vgs_max: vgsEnd,
      vds_min: vdsStart, vds_max: vdsEnd,
      step, enable_rc: physicsParams.enable_rc,
      max_iterations: physicsParams.max_iterations,
      error_tolerance: physicsParams.error_tolerance,
      data_params: physicsParams.data_params,
    });
  };

  if (store.loading) {
    return (
      <div style={{ textAlign: 'center', padding: 100 }}>
        <Spin size="large" tip="Loading..." />
      </div>
    );
  }

  return (
    <div style={{ height: 'calc(100vh - 40px)', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '4px 8px', background: '#f0f0f0', borderBottom: '1px solid #d0d0d0' }}>
        <Button type="text" size="small" icon={<ArrowLeftOutlined />} onClick={() => navigate('/files')}>
          Back
        </Button>
        <span style={{ marginLeft: 12, fontSize: 14, fontWeight: 'bold' }}>Analysis: File #{fileId}</span>
      </div>

      <div className="toolbar">
        <Button size="small" icon={<LineChartOutlined />} loading={plotting} onClick={handlePlot}>Plot</Button>
        <Button size="small" icon={<ThunderboltOutlined />} loading={store.simLoading} onClick={() => setSimDialogOpen(true)}>Simulation</Button>
        <Button size="small" loading={fitting} onClick={handleAutoFitting}>Auto Fitting</Button>
        <div className="toolbar-separator" />
        <Radio.Group size="small" value={store.isAppendMode ? 'append' : 'replace'} onChange={() => store.toggleAppendMode()} optionType="button" buttonStyle="solid">
          <Radio.Button value="append">Append</Radio.Button>
          <Radio.Button value="replace">Replace</Radio.Button>
        </Radio.Group>
        <div className="toolbar-separator" />
        <Radio.Group size="small" value={store.isLogScale ? 'log' : 'linear'} onChange={() => store.toggleLogScale()} optionType="button" buttonStyle="solid">
          <Radio.Button value="linear">Linear</Radio.Button>
          <Radio.Button value="log">Log</Radio.Button>
        </Radio.Group>
        <div className="toolbar-separator" />
        <Button size="small" danger icon={<ScissorOutlined />} disabled={store.curves.length === 0} onClick={() => store.clearCurves()}>Delete All</Button>
      </div>

      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        <div style={{ flex: 1, padding: 4, minWidth: 0 }}>
          <div className="plot-container" style={{ height: '100%' }}>
            <PlotPanel />
          </div>
        </div>

        <div style={{ width: 5, background: '#ccc' }} />

        <div style={{ width: 420, overflowY: 'auto', background: '#fff', padding: 8, borderLeft: '1px solid #d0d0d0' }}>
          <p className="section-header">exp</p>
          <div className="param-box">
            <div style={{ display: 'grid', gridTemplateColumns: '80px 1fr', gap: '6px 8px', alignItems: 'center' }}>
              <span className="param-label">W(um):</span>
              <Select size="small" style={{ width: '100%' }} value={store.selectedW ?? undefined} onChange={store.setW} options={store.wOptions.map((w) => ({ value: w, label: w.toFixed(6) }))} />
              <span className="param-label">L(um):</span>
              <Select size="small" style={{ width: '100%' }} value={store.selectedL ?? undefined} onChange={store.setL} options={store.lOptions.map((l) => ({ value: l, label: l.toFixed(6) }))} />
              <span className="param-label">Type:</span>
              <Select size="small" style={{ width: '100%' }} value={store.selectedType} onChange={store.setType} options={[{ value: 'output', label: 'output' }, { value: 'transfer', label: 'transfer' }]} />
              <span className="param-label">{store.selectedType === 'output' ? 'Vgs:' : 'Vds:'}</span>
              <Select size="small" style={{ width: '100%' }} value={store.selectedV ?? undefined} onChange={store.setV} options={store.vOptions.map((v) => ({ value: v, label: v.toFixed(3) }))} />
            </div>
          </div>

          <p className="section-header" style={{ marginTop: 12 }}>sim</p>
          <div className="param-box">
            <div style={{ display: 'grid', gridTemplateColumns: '70px 1fr 60px 1fr 16px', gap: '6px 4px', alignItems: 'center' }}>
              <span className="param-label">Type:</span>
              <Select size="small" style={{ width: '100%' }} value={simType} onChange={(v) => setSimType(v)} options={[{ value: 'output', label: 'output' }, { value: 'transfer', label: 'transfer' }]} />
              <span /><span /><span />
              <span className="param-label">W(um):</span>
              <InputNumber size="small" style={{ width: '100%' }} value={simW} onChange={(v) => setSimW(v || 0)} step={0.1} />
              <span className="param-label" style={{ textAlign: 'center' }}>L(um):</span>
              <InputNumber size="small" style={{ width: '100%' }} value={simL} onChange={(v) => setSimL(v || 0)} step={0.1} />
              <span />
              <span className="param-label">Vgs Range:</span>
              <InputNumber size="small" style={{ width: '100%' }} value={vgsStart} onChange={(v) => setVgsStart(v || 0)} step={0.1} />
              <span style={{ textAlign: 'center' }}>to</span>
              <InputNumber size="small" style={{ width: '100%' }} value={vgsEnd} onChange={(v) => setVgsEnd(v || 0)} step={0.1} />
              <span>V</span>
              <span className="param-label">Vds Range:</span>
              <InputNumber size="small" style={{ width: '100%' }} value={vdsStart} onChange={(v) => setVdsStart(v || 0)} step={0.1} />
              <span style={{ textAlign: 'center' }}>to</span>
              <InputNumber size="small" style={{ width: '100%' }} value={vdsEnd} onChange={(v) => setVdsEnd(v || 0)} step={0.1} />
              <span>V</span>
              <span className="param-label">Step:</span>
              <InputNumber size="small" style={{ width: '100%' }} value={step} onChange={(v) => setStep(v || 0.1)} step={0.1} min={0.001} />
              <span /><span /><span />
            </div>
          </div>

          {store.curves.length > 0 && (
            <>
              <p className="section-header" style={{ marginTop: 12 }}>Curves</p>
              <div className="param-box" style={{ padding: 8 }}>
                {store.curves.map((c) => (
                  <div key={c.id} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                    <Checkbox checked={c.visible} onChange={() => store.toggleCurveVisible(c.id)} />
                    <span style={{ color: c.color, fontSize: 14 }}>&#9679;</span>
                    <span style={{ flex: 1, fontSize: 12 }}>{c.name}</span>
                    <Tag color={c.source === 'exp' ? 'blue' : 'orange'} style={{ margin: 0 }}>{c.source === 'exp' ? 'Exp' : 'Sim'}</Tag>
                    <Button size="small" type="text" danger icon={<DeleteOutlined />} onClick={() => store.removeCurve(c.id)} />
                  </div>
                ))}
              </div>
            </>
          )}

          {store.fittingResults && (
            <>
              <p className="section-header" style={{ marginTop: 12 }}>Fitting Results</p>
              <div className="param-box" style={{ fontSize: 12 }}>
                <div style={{ marginBottom: 4 }}><strong>V_th:</strong> {store.fittingResults.V_th} V</div>
                <div style={{ marginBottom: 4 }}><strong>U_FE_1:</strong> {store.fittingResults.U_FE_1.join(', ')}</div>
                <div style={{ marginBottom: 4 }}><strong>U_FE_2:</strong> {store.fittingResults.U_FE_2.join(', ')}</div>
                <div><strong>SS:</strong> {store.fittingResults.SS.join(', ')} mV/dec</div>
              </div>
            </>
          )}
        </div>
      </div>

      <SimulationDialog open={simDialogOpen} onClose={() => setSimDialogOpen(false)} onSimulate={handleSimulate} />
    </div>
  );
}
