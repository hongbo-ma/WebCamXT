import { Card, Form, Input, Button, Typography, App } from 'antd';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { authApi } from '../api/auth';
import { useAuthStore } from '../stores/authStore';

const { Title } = Typography;

export function RegisterPage() {
  const navigate = useNavigate();
  const { message } = App.useApp();
  const login = useAuthStore((s) => s.login);
  const [searchParams] = useSearchParams();
  const [form] = Form.useForm();

  const onFinish = async (values: { username: string; password: string; email?: string; invite_code: string }) => {
    try {
      const { data } = await authApi.register(values);
      login(data.token, data.user);
      message.success('Registration successful');
      navigate('/files');
    } catch (err: any) {
      message.error(err.response?.data?.error || 'Registration failed');
    }
  };

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', background: '#f0f0f0' }}>
      <Card style={{ width: 380, border: '1px solid #d0d0d0' }}>
        <Title level={3} style={{ textAlign: 'center', marginBottom: 32, color: '#333' }}>
          CAM-XT Register
        </Title>
        <Form
          form={form}
          onFinish={onFinish}
          layout="vertical"
          initialValues={{ invite_code: searchParams.get('code') || '' }}
        >
          <Form.Item name="invite_code" label="Invite Code" rules={[{ required: true, message: 'Please enter invite code' }]}>
            <Input placeholder="Enter invite code" />
          </Form.Item>
          <Form.Item name="username" label="Username" rules={[{ required: true, message: 'Please enter username' }]}>
            <Input placeholder="Enter username" />
          </Form.Item>
          <Form.Item name="password" label="Password" rules={[{ required: true, message: 'Please enter password' }]}>
            <Input.Password placeholder="Enter password" />
          </Form.Item>
          <Form.Item name="email" label="Email (optional)">
            <Input placeholder="Enter email" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block>
              Register
            </Button>
          </Form.Item>
          <div style={{ textAlign: 'center' }}>
            Already have an account? <Link to="/login">Login</Link>
          </div>
        </Form>
      </Card>
    </div>
  );
}
