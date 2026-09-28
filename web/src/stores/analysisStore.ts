import { create } from 'zustand';
import { filesApi } from '../api/files';
import { analysisApi } from '../api/analysis';
import type { Combinations, Curve, DataParams, FittingResults, SimResponse } from '../types';

const COLORS = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f'];
let colorIdx = 0;
const nextColor = () => COLORS[colorIdx++ % COLORS.length];

interface AnalysisStore {
  fileId: number | null;
  combinations: Combinations | null;
  loading: boolean;

  selectedW: number | null;
  selectedL: number | null;
  selectedType: 'output' | 'transfer';
  selectedV: number | null;

  wOptions: number[];
  lOptions: number[];
  vOptions: number[];

  curves: Curve[];
  isAppendMode: boolean;
  isLogScale: boolean;

  fittingResults: FittingResults | null;
  simLoading: boolean;

  loadFile: (fileId: number) => Promise<void>;
  setW: (w: number) => void;
  setL: (l: number) => void;
  setType: (t: 'output' | 'transfer') => void;
  setV: (v: number) => void;
  toggleAppendMode: () => void;
  toggleLogScale: () => void;
  plot: () => Promise<void>;
  autoFitting: (dataParams: DataParams) => Promise<void>;
  simulate: (simParams: any) => Promise<SimResponse | null>;
  removeCurve: (id: string) => void;
  toggleCurveVisible: (id: string) => void;
  clearCurves: () => void;
}

export const useAnalysisStore = create<AnalysisStore>((set, get) => ({
  fileId: null,
  combinations: null,
  loading: false,
  selectedW: null,
  selectedL: null,
  selectedType: 'output',
  selectedV: null,
  wOptions: [],
  lOptions: [],
  vOptions: [],
  curves: [],
  isAppendMode: true,
  isLogScale: false,
  fittingResults: null,
  simLoading: false,

  loadFile: async (fileId: number) => {
    set({ loading: true });
    try {
      const { data } = await filesApi.get(fileId);
      const combos = data.combinations;
      if (!combos) {
        set({ loading: false });
        return;
      }
      const wOptions = [...new Set(combos.w_l_pairs.map((p) => p.w))].sort((a, b) => a - b);
      const firstW = wOptions[0];
      const lOptions = combos.w_l_pairs.filter((p) => p.w === firstW).map((p) => p.l).sort((a, b) => a - b);
      const firstL = lOptions[0];
      const key = `${firstW}_${firstL}`;
      const vgsList = combos.vgs_vds_map[key]?.vgs || [];
      const vOptions = vgsList;
      set({
        fileId,
        combinations: combos,
        loading: false,
        selectedW: firstW,
        selectedL: firstL,
        selectedType: 'output',
        selectedV: vOptions.length > 0 ? vOptions[vOptions.length - 1] : null,
        wOptions,
        lOptions,
        vOptions,
        curves: [],
        fittingResults: null,
      });
    } catch {
      set({ loading: false });
      throw new Error('加载文件失败');
    }
  },

  setW: (w: number) => {
    const { combinations, selectedType } = get();
    if (!combinations) return;
    const lOptions = combinations.w_l_pairs.filter((p) => p.w === w).map((p) => p.l).sort((a, b) => a - b);
    const firstL = lOptions[0];
    const key = `${w}_${firstL}`;
    const vgsList = combinations.vgs_vds_map[key]?.vgs || [];
    const vdsList = combinations.vgs_vds_map[key]?.vds || [];
    const vOptions = selectedType === 'output' ? vgsList : vdsList;
    set({
      selectedW: w,
      selectedL: firstL,
      lOptions,
      vOptions,
      selectedV: vOptions.length > 0 ? vOptions[vOptions.length - 1] : null,
    });
  },

  setL: (l: number) => {
    const { combinations, selectedW, selectedType } = get();
    if (!combinations || selectedW === null) return;
    const key = `${selectedW}_${l}`;
    const vgsList = combinations.vgs_vds_map[key]?.vgs || [];
    const vdsList = combinations.vgs_vds_map[key]?.vds || [];
    const vOptions = selectedType === 'output' ? vgsList : vdsList;
    set({
      selectedL: l,
      vOptions,
      selectedV: vOptions.length > 0 ? vOptions[vOptions.length - 1] : null,
    });
  },

  setType: (t: 'output' | 'transfer') => {
    const { combinations, selectedW, selectedL } = get();
    if (!combinations || selectedW === null || selectedL === null) {
      set({ selectedType: t });
      return;
    }
    const key = `${selectedW}_${selectedL}`;
    const vgsList = combinations.vgs_vds_map[key]?.vgs || [];
    const vdsList = combinations.vgs_vds_map[key]?.vds || [];
    const vOptions = t === 'output' ? vgsList : vdsList;
    set({
      selectedType: t,
      vOptions,
      selectedV: vOptions.length > 0 ? vOptions[vOptions.length - 1] : null,
    });
  },

  setV: (v: number) => set({ selectedV: v }),
  toggleAppendMode: () => set((s) => ({ isAppendMode: !s.isAppendMode })),
  toggleLogScale: () => set((s) => ({ isLogScale: !s.isLogScale })),

  plot: async () => {
    const { fileId, selectedW, selectedL, selectedType, selectedV, isAppendMode, curves } = get();
    if (!fileId || selectedW === null || selectedL === null || selectedV === null) return;
    try {
      const { data } = await analysisApi.plotData({
        file_id: fileId,
        w: selectedW,
        l: selectedL,
        type: selectedType,
        v_value: selectedV,
      });
      const vLabel = selectedType === 'output' ? `Vgs=${selectedV}` : `Vds=${selectedV}`;
      const newCurve: Curve = {
        id: `exp_${Date.now()}`,
        name: `Exp W${selectedW}L${selectedL} ${vLabel}`,
        source: 'exp',
        x: data.x,
        y: data.y,
        visible: true,
        color: nextColor(),
      };
      set({
        curves: isAppendMode ? [...curves, newCurve] : [newCurve],
      });
    } catch (err) {
      throw err;
    }
  },

  autoFitting: async (dataParams: DataParams) => {
    const { fileId, selectedW, selectedL } = get();
    if (!fileId || selectedW === null || selectedL === null) return;
    const { data } = await analysisApi.autoFitting({
      file_id: fileId,
      w: selectedW,
      l: selectedL,
      data_params: dataParams,
    });
    set({ fittingResults: data });
  },

  simulate: async (simParams: any) => {
    const { fileId, selectedW, selectedL, isAppendMode, curves } = get();
    if (!fileId || selectedW === null || selectedL === null) return null;
    set({ simLoading: true });
    try {
      const { data } = await analysisApi.simulation(simParams);
      const vLabel = simParams.type_sel === 0 ? `Vgs=${simParams.vgs_min}` : `Vds=${simParams.vds_min}`;
      const newCurve: Curve = {
        id: `sim_${Date.now()}`,
        name: `Sim W${selectedW}L${selectedL} ${vLabel}`,
        source: 'sim',
        x: data.x,
        y: data.y,
        visible: true,
        color: nextColor(),
      };
      set({
        curves: isAppendMode ? [...curves, newCurve] : [newCurve],
        simLoading: false,
      });
      return data;
    } catch {
      set({ simLoading: false });
      throw new Error('仿真失败');
    }
  },

  removeCurve: (id: string) => set((s) => ({ curves: s.curves.filter((c) => c.id !== id) })),
  toggleCurveVisible: (id: string) =>
    set((s) => ({
      curves: s.curves.map((c) => (c.id === id ? { ...c, visible: !c.visible } : c)),
    })),
  clearCurves: () => set({ curves: [], fittingResults: null }),
}));
