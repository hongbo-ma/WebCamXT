import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { App as AntApp, ConfigProvider, theme } from 'antd';
import { Layout } from './components/Layout';
import { AuthGuard, AdminGuard } from './components/AuthGuard';
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';
import { FilesPage } from './pages/FilesPage';
import { AnalysisPage } from './pages/AnalysisPage';
import { InvitesPage } from './pages/admin/InvitesPage';
import { UsersPage } from './pages/admin/UsersPage';

function App() {
  return (
    <ConfigProvider
      theme={{
        algorithm: theme.defaultAlgorithm,
        token: {
          colorPrimary: '#0078d4',
          borderRadius: 3,
          colorBorder: '#d0d0d0',
          colorBgLayout: '#ffffff',
          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
          fontSize: 14,
        },
        components: {
          Menu: {
            itemBg: '#f0f0f0',
            horizontalItemSelectedBg: '#e5f1fb',
            itemSelectedColor: '#0078d4',
          },
          Card: {
            headerFontSize: 14,
          },
          Layout: {
            headerBg: '#f0f0f0',
            headerHeight: 40,
          },
        },
      }}
    >
      <AntApp>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route
              element={
                <AuthGuard>
                  <Layout />
                </AuthGuard>
              }
            >
              <Route path="/files" element={<FilesPage />} />
              <Route path="/analysis/:fileId" element={<AnalysisPage />} />
              <Route
                path="/admin/invites"
                element={
                  <AdminGuard>
                    <InvitesPage />
                  </AdminGuard>
                }
              />
              <Route
                path="/admin/users"
                element={
                  <AdminGuard>
                    <UsersPage />
                  </AdminGuard>
                }
              />
            </Route>
            <Route path="*" element={<Navigate to="/files" replace />} />
          </Routes>
        </BrowserRouter>
      </AntApp>
    </ConfigProvider>
  );
}

export default App;
