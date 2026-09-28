import { useEffect, useState } from 'react';
import { Table, Button, Space, Card, Typography, App, Popconfirm, Modal, InputNumber, Tag } from 'antd';
import { PlusOutlined, CopyOutlined, DeleteOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { adminApi } from '../../api/admin';
import type { InviteCode } from '../../types';

const { Title } = Typography;

export function InvitesPage() {
  const { message } = App.useApp();
  const [invites, setInvites] = useState<InviteCode[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [expireDays, setExpireDays] = useState(7);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await adminApi.listInvites();
      setInvites(data.invites);
    } catch {
      message.error('Failed to load invites');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleCreate = async () => {
    try {
      await adminApi.createInvite(expireDays);
      message.success('Invite code generated');
      setModalOpen(false);
      load();
    } catch {
      message.error('Failed to generate invite');
    }
  };

  const handleRevoke = async (id: number) => {
    try {
      await adminApi.revokeInvite(id);
      message.success('Revoked');
      load();
    } catch (err: any) {
      message.error(err.response?.data?.error || 'Revoke failed');
    }
  };

  const copyLink = (code: string) => {
    navigator.clipboard.writeText(`${window.location.origin}/register?code=${code}`);
    message.success('Registration link copied');
  };

  const columns: ColumnsType<InviteCode> = [
    { title: 'Code', dataIndex: 'code', key: 'code', render: (code: string) => (
      <Space>
        <span style={{ fontFamily: 'monospace', fontWeight: 'bold' }}>{code}</span>
        <Button size="small" icon={<CopyOutlined />} onClick={() => copyLink(code)} />
      </Space>
    )},
    { title: 'Status', key: 'status', width: 100, render: (_, r) => {
      if (!r.is_active) return <Tag color="red">Revoked</Tag>;
      if (r.is_used) return <Tag color="green">Used</Tag>;
      return <Tag color="blue">Active</Tag>;
    }},
    { title: 'Used By', key: 'used_by', width: 120, render: (_, r) => r.used_by_username || '-' },
    { title: 'Created', dataIndex: 'created_at', key: 'created_at', width: 180, render: (t: string) => t ? new Date(t).toLocaleString() : '' },
    { title: 'Expires', dataIndex: 'expires_at', key: 'expires_at', width: 180, render: (t: string) => t ? new Date(t).toLocaleString() : '' },
    { title: 'Action', key: 'action', width: 80, render: (_, r) => (!r.is_used && r.is_active ? (
      <Popconfirm title="Revoke this invite?" onConfirm={() => handleRevoke(r.id)}>
        <Button danger size="small" icon={<DeleteOutlined />}>Revoke</Button>
      </Popconfirm>
    ) : null) },
  ];

  return (
    <div style={{ padding: 16 }}>
      <Title level={4} style={{ marginBottom: 16 }}>Invite Management</Title>
      <Card variant="outlined" style={{ border: '1px solid #d0d0d0' }}>
        <Button type="primary" icon={<PlusOutlined />} style={{ marginBottom: 16 }} onClick={() => setModalOpen(true)}>Generate Invite</Button>
        <Table columns={columns} dataSource={invites} rowKey="id" loading={loading} pagination={false} size="middle" />
      </Card>
      <Modal title="Generate Invite" open={modalOpen} onOk={handleCreate} onCancel={() => setModalOpen(false)}>
        <Space><span>Expire (days):</span><InputNumber min={1} max={30} value={expireDays} onChange={(v) => setExpireDays(v || 7)} /></Space>
      </Modal>
    </div>
  );
}
