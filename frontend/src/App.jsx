import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from './context/AuthContext';
import { useAuth } from './context/useAuth';
import { ThemeProvider } from './context/ThemeContext';

// Import layouts
import PatientLayout from './layouts/PatientLayout';
import DoctorLayout from './layouts/DoctorLayout';
import AdminLayout from './layouts/AdminLayout';

// Import guards
import ProtectedRoute from './routes/ProtectedRoute';
import RoleProtectedRoute from './routes/RoleProtectedRoute';

// Import pages
import Login from './pages/common/Login';
import NotFound from './pages/common/NotFound';

// Patient pages
import PatientDashboard from './pages/patient/PatientDashboard';
import BookAppointment from './pages/patient/BookAppointment';
import PatientHistory from './pages/patient/PatientHistory';
import PatientProfile from './pages/patient/PatientProfile';

// Doctor pages
import DoctorDashboard from './pages/doctor/DoctorDashboard';
import HomeVisits from './pages/doctor/HomeVisits';

// Admin pages
import AdminDashboard from './pages/admin/AdminDashboard';
import PatientsList from './pages/admin/PatientsList';
import DoctorsList from './pages/admin/DoctorsList';
import Analytics from './pages/admin/Analytics';
import Billing from './pages/admin/Billing';
import Settings from './pages/admin/Settings';
import AppointmentBooking from './pages/admin/AppointmentBooking';
import Notifications from './pages/admin/Notifications';
import AdminPatientEdit from './pages/admin/AdminPatientEdit';
import AdminPatientHistory from './pages/admin/AdminPatientHistory';
import PatientsCreate from './pages/admin/PatientsCreate';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function HomeRedirect() {
  const { user, isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  const routes = {
    patient: '/patient/dashboard',
    doctor: '/doctor/dashboard',
    admin: '/admin/dashboard',
  };

  return <Navigate to={routes[user.role] || '/login'} replace />;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <AuthProvider>
          <BrowserRouter>
            <Routes>
              {/* Public route */}
              <Route path="/login" element={<Login />} />

              {/* Home redirect based on logged-in role */}
              <Route
                path="/"
                element={
                  <ProtectedRoute>
                    <HomeRedirect />
                  </ProtectedRoute>
                }
              />
              {/* Notifications route (accessible to all authenticated users) */}
              <Route path="/notifications" element={
                <ProtectedRoute>
                  <Notifications />
                </ProtectedRoute>
              } />

              {/* Patient Routes */}
              <Route
                path="/patient"
                element={
                  <ProtectedRoute>
                    <RoleProtectedRoute allowedRoles={['patient']}>
                      <PatientLayout />
                    </RoleProtectedRoute>
                  </ProtectedRoute>
                }
              >
                <Route path="dashboard" element={<PatientDashboard />} />
                <Route path="book" element={<BookAppointment />} />
                <Route path="history" element={<PatientHistory />} />
                <Route path="profile" element={<PatientProfile />} />
              </Route>

              {/* Doctor Routes */}
              <Route
                path="/doctor"
                element={
                  <ProtectedRoute>
                    <RoleProtectedRoute allowedRoles={['doctor']}>
                      <DoctorLayout />
                    </RoleProtectedRoute>
                  </ProtectedRoute>
                }
              >
                <Route path="dashboard" element={<DoctorDashboard />} />
                <Route path="patients" element={<PatientsList />} />
                <Route path="home-visits" element={<HomeVisits />} />
                <Route path="settings" element={<Settings />} />
              </Route>

              {/* Admin Routes */}
              <Route
                path="/admin"
                element={
                  <ProtectedRoute>
                    <RoleProtectedRoute allowedRoles={['admin']}>
                      <AdminLayout />
                    </RoleProtectedRoute>
                  </ProtectedRoute>
                }
              >
                <Route path="dashboard" element={<AdminDashboard />} />
                <Route path="patients" element={<PatientsList />} />
                <Route path="patients-create" element={<PatientsCreate />} />
                <Route path="patients-edit/:id" element={<AdminPatientEdit />} />
                <Route path="patients-history/:id" element={<AdminPatientHistory />} />
                <Route path="doctors" element={<DoctorsList />} />
                <Route path="analytics" element={<Analytics />} />
                <Route path="billing" element={<Billing />} />
                <Route path="settings" element={<Settings />} />
                <Route path="appointment-booking" element={<AppointmentBooking />} />
              </Route>

              {/* 404 Fallback */}
              <Route path="*" element={<NotFound />} />
            </Routes>
          </BrowserRouter>
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}