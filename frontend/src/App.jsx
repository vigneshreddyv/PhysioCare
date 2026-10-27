import React, { Component, lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from './context/AuthContext';
import { useAuth } from './context/useAuth';
import { ThemeProvider } from './context/ThemeContext';

// Import guards
import ProtectedRoute from './routes/ProtectedRoute';
import RoleProtectedRoute from './routes/RoleProtectedRoute';

// Route-level modules stay out of the public entry bundle until their route is requested.
const PatientLayout = lazy(() => import('./layouts/PatientLayout'));
const DoctorLayout = lazy(() => import('./layouts/DoctorLayout'));
const AdminLayout = lazy(() => import('./layouts/AdminLayout'));

const Login = lazy(() => import('./pages/common/Login'));
const EmailLogin = lazy(() => import('./pages/common/EmailLogin'));
const PhoneVerification = lazy(() => import('./pages/common/PhoneVerification'));
const PhoneCodePreview = lazy(() => import('./pages/common/PhoneCodePreview'));
const Register = lazy(() => import('./pages/common/Register'));
const PublicHome = lazy(() => import('./pages/common/PublicHome'));
const NotFound = lazy(() => import('./pages/common/NotFound'));

const PatientDashboard = lazy(() => import('./pages/patient/PatientDashboard'));
const BookAppointment = lazy(() => import('./pages/patient/BookAppointment'));
const PatientHistory = lazy(() => import('./pages/patient/PatientHistory'));
const PatientProfile = lazy(() => import('./pages/patient/PatientProfile'));
const HomeVisitRequests = lazy(() => import('./pages/patient/HomeVisitRequests'));
const PatientServices = lazy(() => import('./pages/patient/PatientServices'));
const ServiceDetails = lazy(() => import('./pages/patient/ServiceDetails'));
const LaboratoryRequests = lazy(() => import('./pages/patient/LaboratoryRequests'));

const DoctorDashboard = lazy(() => import('./pages/doctor/DoctorDashboard'));
const HomeVisits = lazy(() => import('./pages/doctor/HomeVisits'));
const DoctorPatientHistory = lazy(() => import('./pages/doctor/DoctorPatientHistory'));

const AdminDashboard = lazy(() => import('./pages/admin/AdminDashboard'));
const PatientsList = lazy(() => import('./pages/admin/PatientsList'));
const DoctorsList = lazy(() => import('./pages/admin/DoctorsList'));
const Analytics = lazy(() => import('./pages/admin/Analytics'));
const Billing = lazy(() => import('./pages/admin/Billing'));
const Settings = lazy(() => import('./pages/admin/Settings'));
const AppointmentBooking = lazy(() => import('./pages/admin/AppointmentBooking'));
const Notifications = lazy(() => import('./pages/admin/Notifications'));
const AdminPatientEdit = lazy(() => import('./pages/admin/AdminPatientEdit'));
const AdminPatientHistory = lazy(() => import('./pages/admin/AdminPatientHistory'));
const PatientsCreate = lazy(() => import('./pages/admin/PatientsCreate'));
const DemoServices = lazy(() => import('./pages/admin/DemoServices'));
const ClinicianSchedules = lazy(() => import('./pages/admin/ClinicianSchedules'));
const ReceptionistDashboard = lazy(() => import('./pages/receptionist/ReceptionistDashboard'));
const LaboratoryDashboard = lazy(() => import('./pages/laboratorian/LaboratoryDashboard'));

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
    receptionist: '/reception/dashboard',
    laboratorian: '/laboratory/dashboard',
  };

  return <Navigate to={routes[user.role] || '/login'} replace />;
}

function RouteLoading() {
  return (
    <main className="route-loading" role="status" aria-live="polite" aria-busy="true">
      <span className="material-symbols-outlined" aria-hidden="true">progress_activity</span>
      <div>
        <strong>Loading this view…</strong>
        <span>Your account and any unsent form details have not been changed.</span>
      </div>
    </main>
  );
}

class RouteChunkBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error) {
    if (import.meta.env.DEV) console.error('A route module could not be loaded.', error);
  }

  render() {
    if (this.state.failed) {
      return (
        <main className="route-loading route-loading--error" role="alert">
          <span className="material-symbols-outlined" aria-hidden="true">cloud_off</span>
          <div>
            <strong>This view could not be loaded.</strong>
            <span>Check your connection, then reload. No form was submitted.</span>
            <button type="button" onClick={() => window.location.reload()}>Reload this view</button>
          </div>
        </main>
      );
    }

    return this.props.children;
  }
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <AuthProvider>
          <BrowserRouter>
            <RouteChunkBoundary>
              <Suspense fallback={<RouteLoading />}>
              <Routes>
              {/* Public routes */}
              <Route path="/" element={<PublicHome />} />
              <Route path="/login" element={<Login />} />
              <Route path="/login/email" element={<EmailLogin />} />
              <Route path="/verify-phone" element={<PhoneVerification />} />
              <Route path="/verify-phone/code" element={<PhoneCodePreview />} />
              <Route path="/register" element={<Register />} />

              {/* Home redirect based on logged-in role */}
              <Route
                path="/app"
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
                <Route path="home-visits" element={<HomeVisitRequests />} />
                <Route path="services" element={<PatientServices />} />
                <Route path="services/:serviceKey" element={<ServiceDetails />} />
                <Route path="laboratory" element={<LaboratoryRequests />} />
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
                <Route path="patients/:patientId" element={<DoctorPatientHistory />} />
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
                <Route path="schedules/:doctorId" element={<ClinicianSchedules />} />
                <Route path="analytics" element={<Analytics />} />
                <Route path="billing" element={<Billing />} />
                <Route path="settings" element={<Settings />} />
                <Route path="appointment-booking" element={<AppointmentBooking />} />
                <Route path="demo-services" element={<DemoServices />} />
              </Route>

              {/* Reception Routes */}
              <Route
                path="/reception"
                element={
                  <ProtectedRoute>
                    <RoleProtectedRoute allowedRoles={['receptionist']}>
                      <AdminLayout />
                    </RoleProtectedRoute>
                  </ProtectedRoute>
                }
              >
                <Route path="dashboard" element={<ReceptionistDashboard />} />
                <Route path="patients" element={<PatientsList />} />
                <Route path="appointment-booking" element={<AppointmentBooking />} />
              </Route>

              {/* 404 Fallback */}
              <Route
                path="/laboratory"
                element={
                  <ProtectedRoute>
                    <RoleProtectedRoute allowedRoles={['laboratorian']}>
                      <AdminLayout />
                    </RoleProtectedRoute>
                  </ProtectedRoute>
                }
              >
                <Route path="dashboard" element={<LaboratoryDashboard />} />
              </Route>

              {/* 404 Fallback */}
              <Route path="*" element={<NotFound />} />
              </Routes>
              </Suspense>
            </RouteChunkBoundary>
          </BrowserRouter>
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
