import { useEffect, useState } from 'react';
import { Table, Button, Card, Typography, App, Popconfirm, Tag, Select } from 'antd';
import { DeleteOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { adminApi } from '../../api/admin';
import { useAuthStore } from '../../stores/authStore';
import type { User } from '../../types';

const { Title } = Typography;

export function UsersPage() {
  const { message } = App.useApp();
  const currentUser = useAuthStore((s) => s.user);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(false);

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

  const columns: ColumnsType<User> = [
    { title: 'Username', dataIndex: 'username', key: 'username' },
    { title: 'Role', dataIndex: 'role', key: 'role', width: 140, render: (role: string, r) =>
      r.id === currentUser?.id ? <Tag color={role === 'admin' ? 'red' : 'blue'}>{role}</Tag> : (
        <Select size="small" value={role} style={{ width: 100 }} onChange={(v) => handleRoleChange(r.id, v as 'admin' | 'user')}
          options={[{ value: 'admin', label: 'admin' }, { value: 'user', label: 'user' }]} />
      )
    },
    { title: 'Email', dataIndex: 'email', key: 'email', render: (e: string) => e || '-' },
    { title: 'Files', dataIndex: 'file_count', key: 'file_count', width: 80 },
    { title: 'Created', dataIndex: 'created_at', key: 'created_at', width: 180, render: (t: string) => t ? new Date(t).toLocaleString() : '' },
    { title: 'Action', key: 'action', width: 80, render: (_, r) => r.id !== currentUser?.id ? (
      <Popconfirm title="Delete this user? All files will be removed." onConfirm={() => handleDelete(r.id)}>
        <Button danger size="small" icon={<DeleteOutlined />}>Delete</Button>
      </Popconfirm>
    ) : null },
  ];

  return (
    <div style={{ padding: 16 }}>
      <Title level={4} style={{ marginBottom: 16 }}>User Management</Title>
      <Card variant="outlined" style={{ border: '1px solid #d0d0d0' }}>
        <Table columns={columns} dataSource={users} rowKey="id" loading={loading} pagination={false} size="middle" />
      </Card>
    </div>
  );
}
