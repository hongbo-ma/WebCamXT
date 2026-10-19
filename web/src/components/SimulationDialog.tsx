import { Modal, Form, InputNumber, Switch, Row, Col, Divider, App, Button } from 'antd';
import { useState } from 'react';
import type { DataParams } from '../types';

/** 态密度数值较大 (1e18 量级), 输入框以指数形式显示, 如 5.1e18 */
const sciFormatter = (value?: number | string): string => {
  if (value === undefined || value === null || value === '') return '';
  const n = typeof value === 'number' ? value : parseFloat(String(value).replace(/[^\d.eE+-]/g, ''));
  if (!isFinite(n)) return String(value);
  if (n === 0) return '0';
  const abs = Math.abs(n);
  if (abs >= 1e5 || abs < 1e-3) {
    return n.toExponential(3).replace(/\.?0+e/, 'e').replace('e+', 'e');
  }
  return String(n);
};

const sciParser = (display?: string): string => (display ?? '').replace(/[^\d.eE+-]/g, '');

interface Props {
  open: boolean;
  onClose: () => void;
  onSimulate: (params: { enable_rc: boolean; max_iterations: number; error_tolerance: number; data_params: DataParams }) => Promise<void>;
}

export function SimulationDialog({ open, onClose, onSimulate }: Props) {
  const { message } = App.useApp();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  const handleOk = async () => {
    try {
      const v = await form.validateFields();
      setLoading(true);
      const dataParams: DataParams = {
        t_tail: v.t_tail, t_deep: v.t_deep, g_tail: v.g_tail, g_deep: v.g_deep,
        T: v.T, mu_free: v.mu_free, Vfb: v.Vfb, phi_F0: v.phi_F0, CoxArea: v.CoxArea, M: v.M,
      };
      await onSimulate({
        enable_rc: v.enable_rc, max_iterations: v.max_iterations,
        error_tolerance: v.error_tolerance, data_params: dataParams,
      });
      message.success('Simulation complete');
      onClose();
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error(err?.message || 'Simulation failed');
    } finally {
      setLoading(false);
    }
  };

  const labelCol = { span: 10 };
  const wrapperCol = { span: 14 };

  return (
    <Modal
      title="Device Simulation Parameters"
      open={open}
      onCancel={onClose}
      width={520}
      footer={[
        <Button key="cancel" onClick={onClose}>Cancel</Button>,
        <Button key="sim" type="primary" loading={loading} onClick={handleOk}>Simulation</Button>,
      ]}
    >
      <Form form={form} layout="horizontal" labelCol={labelCol} wrapperCol={wrapperCol} initialValues={{
        t_tail: 348.17, t_deep: 580.28, g_tail: 5.1e18, g_deep: 2.463e18,
        T: 300, mu_free: 0.8, Vfb: -0.8, phi_F0: 0.4, CoxArea: 0.03, M: 0.2,
        enable_rc: false, max_iterations: 100, error_tolerance: 0.01,
      }}>
        <Divider plain>Physics Parameters</Divider>
        <Row>
          <Col span={12}><Form.Item name="t_tail" label="T_tail(K)" rules={[{ required: true }]}><InputNumber style={{ width: '100%' }} /></Form.Item></Col>
          <Col span={12}><Form.Item name="t_deep" label="T_deep(K)" rules={[{ required: true }]}><InputNumber style={{ width: '100%' }} /></Form.Item></Col>
        </Row>
        <Row>
          <Col span={12}><Form.Item name="g_tail" label="g_tail" rules={[{ required: true }]}><InputNumber style={{ width: '100%' }} step={1e17} formatter={sciFormatter} parser={sciParser} /></Form.Item></Col>
          <Col span={12}><Form.Item name="g_deep" label="g_deep" rules={[{ required: true }]}><InputNumber style={{ width: '100%' }} step={1e17} formatter={sciFormatter} parser={sciParser} /></Form.Item></Col>
        </Row>
        <Row>
          <Col span={12}><Form.Item name="T" label="T(K)" rules={[{ required: true }]}><InputNumber style={{ width: '100%' }} /></Form.Item></Col>
          <Col span={12}><Form.Item name="mu_free" label="mu_free" rules={[{ required: true }]}><InputNumber step={0.1} style={{ width: '100%' }} /></Form.Item></Col>
        </Row>
        <Row>
          <Col span={12}><Form.Item name="Vfb" label="Vfb(V)" rules={[{ required: true }]}><InputNumber step={0.1} style={{ width: '100%' }} /></Form.Item></Col>
          <Col span={12}><Form.Item name="phi_F0" label="phi_F0(V)" rules={[{ required: true }]}><InputNumber step={0.01} style={{ width: '100%' }} /></Form.Item></Col>
        </Row>
        <Row>
          <Col span={12}><Form.Item name="CoxArea" label="CoxArea" rules={[{ required: true }]}><InputNumber step={0.001} style={{ width: '100%' }} /></Form.Item></Col>
          <Col span={12}><Form.Item name="M" label="Warp Effect"><InputNumber step={0.001} style={{ width: '100%' }} /></Form.Item></Col>
        </Row>

        <Divider plain>RC Settings</Divider>
        <Form.Item name="enable_rc" label="Enable RC" valuePropName="checked"><Switch /></Form.Item>
        <Form.Item name="max_iterations" label="Max Iterations"><InputNumber style={{ width: '100%' }} /></Form.Item>
        <Form.Item name="error_tolerance" label="Error Tolerance"><InputNumber step={0.001} style={{ width: '100%' }} /></Form.Item>
      </Form>
    </Modal>
  );
}
