import { Layout as AntLayout, Menu, Button, Dropdown, Space } from 'antd';
import { UserOutlined, LogoutOutlined, FileOutlined, DownOutlined } from '@ant-design/icons';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';

const { Header, Content } = AntLayout;

export function Layout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuthStore();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const menuItems = [
    { key: '/files', label: 'Files', icon: <FileOutlined /> },
  ];

  if (user?.role === 'admin') {
    menuItems.push(
      { key: '/admin/invites', label: 'Invites', icon: <UserOutlined /> },
      { key: '/admin/users', label: 'Users', icon: <UserOutlined /> },
    );
  }

  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      <Header style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        height: 40,
        lineHeight: '40px',
        padding: '0 16px',
        background: '#f0f0f0',
        borderBottom: '1px solid #d0d0d0',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <strong style={{ fontSize: 14, color: '#333' }}>CAM-XT</strong>
          <Menu
            mode="horizontal"
            selectedKeys={[location.pathname]}
            items={menuItems}
            onClick={({ key }) => navigate(key)}
            style={{
              flex: 1,
              minWidth: 0,
              background: 'transparent',
              borderBottom: 'none',
              lineHeight: '38px',
            }}
          />
        </div>
        <Dropdown
          menu={{
            items: [
              {
                key: 'logout',
                label: 'Logout',
                icon: <LogoutOutlined />,
                onClick: handleLogout,
              },
            ],
          }}
        >
          <Button type="text" size="small">
            <Space>
              <UserOutlined />
              {user?.username}
              <DownOutlined style={{ fontSize: 10 }} />
            </Space>
          </Button>
        </Dropdown>
      </Header>
      <Content style={{ padding: '0', background: '#fff' }}>
        <Outlet />
      </Content>
    </AntLayout>
  );
}
