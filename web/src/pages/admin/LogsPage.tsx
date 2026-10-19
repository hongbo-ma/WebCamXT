import { useEffect, useState, useCallback } from 'react';
import { Table, Card, Typography, App, Tag, Select, Space, Button } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { adminApi } from '../../api/admin';
import type { OperationLog, User } from '../../types';

const { Title } = Typography;

const ACTION_META: Record<string, { label: string; color: string }> = {
  upload: { label: 'Upload', color: 'green' },
  delete: { label: 'Delete', color: 'red' },
  plot: { label: 'Plot', color: 'blue' },
  simulation: { label: 'Simulation', color: 'orange' },
  auto_fitting: { label: 'Auto Fitting', color: 'purple' },
  renew: { label: 'Renew', color: 'cyan' },
};

const PAGE_SIZE = 20;

export function LogsPage() {
  const { message } = App.useApp();
  const [logs, setLogs] = useState<OperationLog[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [users, setUsers] = useState<User[]>([]);
  const [filterUser, setFilterUser] = useState<number | undefined>();
  const [filterAction, setFilterAction] = useState<string | undefined>();

  const load = useCallback(async (p: number, userId?: number, action?: string) => {
    setLoading(true);
    try {
      const { data } = await adminApi.listLogs({
        page: p, page_size: PAGE_SIZE,
        ...(userId ? { user_id: userId } : {}),
        ...(action ? { action } : {}),
      });
      setLogs(data.logs);
      setTotal(data.total);
    } catch {
      message.error('Failed to load logs');
    } finally {
      setLoading(false);
    }
  }, [message]);

  useEffect(() => {
    adminApi.listUsers().then(({ data }) => setUsers(data.users)).catch(() => {});
  }, []);

  useEffect(() => {
    load(page, filterUser, filterAction);
  }, [page, filterUser, filterAction, load]);

  const columns: ColumnsType<OperationLog> = [
    { title: 'Time', dataIndex: 'created_at', key: 'created_at', width: 170,
      render: (t: string) => (t ? new Date(t).toLocaleString() : '') },
    { title: 'User', dataIndex: 'username', key: 'username', width: 130 },
    { title: 'Action', dataIndex: 'action', key: 'action', width: 120,
      render: (a: string) => {
        const meta = ACTION_META[a];
        return <Tag color={meta?.color || 'default'}>{meta?.label || a}</Tag>;
      } },
    { title: 'File', dataIndex: 'file_name', key: 'file_name',
      render: (name: string | null, r) => {
        if (!name && !r.file_id) return '-';
        return (
          <span>
            {name || `file #${r.file_id}`}
            {r.file_owner_name && r.file_owner_name !== r.username && (
              <Tag style={{ marginLeft: 6 }} color="geekblue">owner: {r.file_owner_name}</Tag>
            )}
          </span>
        );
      } },
    { title: 'Detail', dataIndex: 'detail', key: 'detail', ellipsis: true,
      render: (d: string | null) => d || '-' },
  ];

  return (
    <div style={{ padding: 16 }}>
      <Title level={4} style={{ marginBottom: 16 }}>Operation Logs</Title>
      <Card variant="outlined" style={{ border: '1px solid #d0d0d0' }}>
        <Space style={{ marginBottom: 16 }} wrap>
          <Select
            allowClear
            placeholder="Filter by user"
            style={{ width: 180 }}
            value={filterUser}
            onChange={(v) => { setPage(1); setFilterUser(v); }}
            options={users.map((u) => ({ value: u.id, label: u.username }))}
          />
          <Select
            allowClear
            placeholder="Filter by action"
            style={{ width: 160 }}
            value={filterAction}
            onChange={(v) => { setPage(1); setFilterAction(v); }}
            options={Object.entries(ACTION_META).map(([value, m]) => ({ value, label: m.label }))}
          />
          <Button icon={<ReloadOutlined />} onClick={() => load(page, filterUser, filterAction)}>Refresh</Button>
        </Space>
        <Table
          columns={columns}
          dataSource={logs}
          rowKey="id"
          loading={loading}
          size="middle"
          pagination={{
            current: page,
            pageSize: PAGE_SIZE,
            total,
            showTotal: (t) => `Total ${t} records`,
            onChange: (p) => setPage(p),
          }}
        />
      </Card>
    </div>
  );
}
