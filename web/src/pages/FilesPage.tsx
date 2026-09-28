import { useEffect, useState } from 'react';
import { Table, Button, Space, Upload, App, Popconfirm, Typography, Card } from 'antd';
import { UploadOutlined, DeleteOutlined, LineChartOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { useNavigate } from 'react-router-dom';
import { filesApi } from '../api/files';
import type { FileRecord } from '../types';

const { Title } = Typography;

export function FilesPage() {
  const navigate = useNavigate();
  const { message } = App.useApp();
  const [files, setFiles] = useState<FileRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);

  const loadFiles = async () => {
    setLoading(true);
    try {
      const { data } = await filesApi.list();
      setFiles(data.files);
    } catch {
      message.error('Failed to load files');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadFiles();
  }, []);

  const handleUpload = async (file: File) => {
    setUploading(true);
    try {
      await filesApi.upload(file);
      message.success('Upload successful');
      loadFiles();
    } catch (err: any) {
      message.error(err.response?.data?.error || 'Upload failed');
    } finally {
      setUploading(false);
    }
    return false;
  };

  const handleDelete = async (id: number) => {
    try {
      await filesApi.delete(id);
      message.success('Deleted');
      loadFiles();
    } catch (err: any) {
      message.error(err.response?.data?.error || 'Delete failed');
    }
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  };

  const columns: ColumnsType<FileRecord> = [
    {
      title: 'Filename',
      dataIndex: 'original_filename',
      key: 'original_filename',
    },
    {
      title: 'Size',
      dataIndex: 'file_size',
      key: 'file_size',
      width: 100,
      render: (size: number) => formatSize(size),
    },
    {
      title: 'Uploaded',
      dataIndex: 'uploaded_at',
      key: 'uploaded_at',
      width: 180,
      render: (t: string) => (t ? new Date(t).toLocaleString() : ''),
    },
    {
      title: 'Action',
      key: 'action',
      width: 160,
      render: (_, record) => (
        <Space>
          <Button
            type="primary"
            size="small"
            icon={<LineChartOutlined />}
            onClick={() => navigate(`/analysis/${record.id}`)}
          >
            Analyze
          </Button>
          <Popconfirm title="Delete this file?" onConfirm={() => handleDelete(record.id)}>
            <Button danger size="small" icon={<DeleteOutlined />}>
              Delete
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 16 }}>
      <Title level={4} style={{ marginBottom: 16 }}>My Files</Title>
      <Card variant="outlined" style={{ border: '1px solid #d0d0d0' }}>
        <Space style={{ marginBottom: 16 }}>
          <Upload
            accept=".xls,.xlsx"
            showUploadList={false}
            beforeUpload={handleUpload}
            disabled={uploading}
          >
            <Button type="primary" icon={<UploadOutlined />} loading={uploading}>
              Upload File
            </Button>
          </Upload>
        </Space>
        <Table
          columns={columns}
          dataSource={files}
          rowKey="id"
          loading={loading}
          pagination={false}
          size="middle"
        />
      </Card>
    </div>
  );
}
