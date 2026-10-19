import { useEffect, useState } from 'react';
import { Table, Button, Card, Typography, App, Popconfirm, Tag, Select, Modal, InputNumber, Checkbox, Space } from 'antd';
import { DeleteOutlined, ClockCircleOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { adminApi } from '../../api/admin';
import { useAuthStore } from '../../stores/authStore';
import type { User } from '../../types';

const { Title, Text } = Typography;

function expiryStatus(u: User): { label: string; color: string } {
  if (u.role === 'admin') return { label: 'Admin', color: 'red' };
  if (!u.expires_at) return { label: 'Permanent', color: 'green' };
  if (u.is_expired) return { label: 'Expired', color: 'default' };
  const days = (new Date(u.expires_at).getTime() - Date.now()) / 86400000;
  if (days < 7) return { label: `Expiring (${Math.ceil(days)}d)`, color: 'orange' };
  return { label: 'Active', color: 'blue' };
}

export function UsersPage() {
  const { message } = App.useApp();
  const currentUser = useAuthStore((s) => s.user);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(false);

  const [renewTarget, setRenewTarget] = useState<User | null>(null);
  const [renewDays, setRenewDays] = useState(30);
  const [renewPermanent, setRenewPermanent] = useState(false);
  const [renewing, setRenewing] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await adminApi.listUsers();
      setUsers(data.users);
    } catch {
      message.error('Failed to load users');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleDelete = async (id: number) => {
    try {
      await adminApi.deleteUser(id);
      message.success('User deleted');
      load();
    } catch (err: any) {
      message.error(err.response?.data?.error || 'Delete failed');
    }
  };

  const handleRoleChange = async (id: number, role: 'admin' | 'user') => {
    try {
      await adminApi.updateUserRole(id, role);
      message.success('Role updated');
      load();
    } catch (err: any) {
      message.error(err.response?.data?.error || 'Update failed');
    }
  };

  const openRenew = (u: User) => {
    setRenewTarget(u);
    setRenewDays(30);
    setRenewPermanent(u.role !== 'admin' && !u.expires_at);
  };

  const handleRenew = async () => {
    if (!renewTarget) return;
    if (!renewPermanent && renewDays <= 0) {
      message.error('Days must be greater than 0');
      return;
    }
    setRenewing(true);
    try {
      await adminApi.updateUserExpiry(
        renewTarget.id,
        renewPermanent ? { permanent: true } : { extend_days: renewDays },
      );
      message.success('Expiry updated');
      setRenewTarget(null);
      load();
    } catch (err: any) {
      message.error(err.response?.data?.error || 'Update failed');
    } finally {
      setRenewing(false);
    }
  };

  const renewPreview = () => {
    if (!renewTarget || renewPermanent) return 'Permanent (never expires)';
    const base = renewTarget.expires_at && new Date(renewTarget.expires_at).getTime() > Date.now()
      ? new Date(renewTarget.expires_at)
      : new Date();
    const next = new Date(base.getTime() + renewDays * 86400000);
    return next.toLocaleString();
  };

  const columns: ColumnsType<User> = [
    { title: 'Username', dataIndex: 'username', key: 'username' },
    { title: 'Role', dataIndex: 'role', key: 'role', width: 120, render: (role: string, r) =>
      r.id === currentUser?.id ? <Tag color={role === 'admin' ? 'red' : 'blue'}>{role}</Tag> : (
        <Select size="small" value={role} style={{ width: 95 }} onChange={(v) => handleRoleChange(r.id, v as 'admin' | 'user')}
          options={[{ value: 'admin', label: 'admin' }, { value: 'user', label: 'user' }]} />
      )
    },
    {
      title: 'Expiry', dataIndex: 'expires_at', key: 'expires_at', width: 180,
      render: (t: string | null, r) => {
        const s = expiryStatus(r);
        return (
          <Space size={4}>
            <Tag color={s.color}>{s.label}</Tag>
            {t && <Text type="secondary" style={{ fontSize: 12 }}>{new Date(t).toLocaleDateString()}</Text>}
          </Space>
        );
      },
    },
    { title: 'Email', dataIndex: 'email', key: 'email', render: (e: string) => e || '-' },
    { title: 'Files', dataIndex: 'file_count', key: 'file_count', width: 70 },
    { title: 'Created', dataIndex: 'created_at', key: 'created_at', width: 160, render: (t: string) => t ? new Date(t).toLocaleString() : '' },
    {
      title: 'Action', key: 'action', width: 200, render: (_, r) => (
        <Space>
          <Button size="small" icon={<ClockCircleOutlined />} onClick={() => openRenew(r)}>Renew</Button>
          {r.id !== currentUser?.id && (
            <Popconfirm title="Delete this user? All files will be removed." onConfirm={() => handleDelete(r.id)}>
              <Button danger size="small" icon={<DeleteOutlined />}>Delete</Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 16 }}>
      <Title level={4} style={{ marginBottom: 16 }}>User Management</Title>
      <Card variant="outlined" style={{ border: '1px solid #d0d0d0' }}>
        <Table columns={columns} dataSource={users} rowKey="id" loading={loading} pagination={false} size="middle" />
      </Card>

      <Modal
        title={renewTarget ? `Renew: ${renewTarget.username}` : ''}
        open={!!renewTarget}
        onCancel={() => setRenewTarget(null)}
        onOk={handleRenew}
        okText="Apply"
        confirmLoading={renewing}
        width={420}
      >
        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          <div>
            <Text type="secondary">Current: </Text>
            <Text>
              {renewTarget?.expires_at
                ? `${new Date(renewTarget.expires_at).toLocaleString()}${renewTarget.is_expired ? ' (expired)' : ''}`
                : 'Permanent'}
            </Text>
          </div>
          <div>
            <Text type="secondary">Extend by (days): </Text>
            <InputNumber
              min={1}
              max={3650}
              value={renewPermanent ? undefined : renewDays}
              disabled={renewPermanent}
              onChange={(v) => setRenewDays(v || 30)}
              style={{ width: 120, marginLeft: 8 }}
            />
          </div>
          <Checkbox checked={renewPermanent} onChange={(e) => setRenewPermanent(e.target.checked)}>
            Permanent (never expires)
          </Checkbox>
          <div>
            <Text type="secondary">New expiry: </Text>
            <Text strong>{renewPreview()}</Text>
          </div>
        </Space>
      </Modal>
    </div>
  );
}
