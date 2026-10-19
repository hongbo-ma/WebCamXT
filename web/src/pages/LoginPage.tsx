import { Card, Form, Input, Button, Typography, App } from 'antd';
import { useEffect } from 'react';
import { useNavigate, Link, useSearchParams } from 'react-router-dom';
import { authApi } from '../api/auth';
import { useAuthStore } from '../stores/authStore';

const { Title } = Typography;

export function LoginPage() {
  const navigate = useNavigate();
  const { message } = App.useApp();
  const login = useAuthStore((s) => s.login);
  const [form] = Form.useForm();
  const [searchParams] = useSearchParams();

  useEffect(() => {
    if (searchParams.get('expired')) {
      message.warning('账号已过期，请联系管理员续期');
    }
  }, [searchParams]);

  const onFinish = async (values: { username: string; password: string }) => {
    try {
      const { data } = await authApi.login(values.username, values.password);
      login(data.token, data.user);
      message.success('Login successful');
      navigate('/files');
    } catch (err: any) {
      message.error(err.response?.data?.error || 'Login failed');
    }
  };

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', background: '#f0f0f0' }}>
      <Card style={{ width: 380, border: '1px solid #d0d0d0' }}>
        <Title level={3} style={{ textAlign: 'center', marginBottom: 32, color: '#333' }}>
          CAM-XT Login
        </Title>
        <Form form={form} onFinish={onFinish} layout="vertical">
          <Form.Item name="username" label="Username" rules={[{ required: true, message: 'Please enter username' }]}>
            <Input placeholder="Enter username" />
          </Form.Item>
          <Form.Item name="password" label="Password" rules={[{ required: true, message: 'Please enter password' }]}>
            <Input.Password placeholder="Enter password" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block>
              Login
            </Button>
          </Form.Item>
          <div style={{ textAlign: 'center' }}>
            No account? <Link to="/register">Register with invite code</Link>
          </div>
        </Form>
      </Card>
    </div>
  );
}
