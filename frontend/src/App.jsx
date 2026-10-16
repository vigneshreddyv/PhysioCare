import LaboratoryPayment from './pages/patient/LaboratoryPayment';
import LaboratoryReview from './pages/patient/LaboratoryReview';
import LaboratoryDateTime from './pages/patient/LaboratoryDateTime';
import HomeVisitLab from './pages/patient/HomeVisitLab';
import LaboratoryTestSelection from './pages/patient/LaboratoryTestSelection';
import ClinicLaboratoryVisit from './pages/patient/ClinicLaboratoryVisit';
import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from './context/AuthContext';
import { useAuth } from './context/useAuth';
import { ThemeProvider } from './context/ThemeContext';
import LaboratorySuccess from './pages/patient/LaboratorySuccess';
import Register from './pages/common/Register';



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
import PatientAppointments from './pages/patient/PatientAppointments';
import ServiceSelection from './pages/patient/ServiceSelection';
import BookAppointment from './pages/patient/BookAppointment';
import PatientHistory from './pages/patient/PatientHistory';
import PatientProfile from './pages/patient/PatientProfile';
import LaboratoryTests from './pages/patient/LaboratoryTests';
import PatientCarePlan from './pages/patient/PatientCarePlan';
import PatientProgress from './pages/patient/PatientProgress';
import PatientExercises from './pages/patient/PatientExercises';
import PatientReports from './pages/patient/PatientReports';
import PatientSettings from './pages/patient/PatientSettings';
import LaboratoryBookingDetail from './pages/patient/LaboratoryBookingDetail';


// Doctor pages
import DoctorDashboard from './pages/doctor/DoctorDashboard';
import HomeVisits from './pages/doctor/HomeVisits';
import PatientSnapshot from './pages/doctor/PatientSnapshot';

// Admin pages
import AdminDashboard from './pages/admin/AdminDashboard';
import PatientsList from './pages/admin/PatientsList';
import DoctorsList from './pages/admin/DoctorsList';
import Analytics from './pages/admin/Analytics';
import Billing from './pages/admin/Billing';
import Settings from './pages/admin/Settings';
import AppointmentBooking from './pages/admin/AppointmentBooking';
import AdminNotifications from './pages/admin/Notifications';
import CommonNotifications from './pages/common/Notifications';
import AdminPatientEdit from './pages/admin/AdminPatientEdit';
import AdminPatientHistory from './pages/admin/AdminPatientHistory';
import PatientsCreate from './pages/admin/PatientsCreate';
import CarePlanManagement from './pages/admin/CarePlanManagement';
import ExerciseAssignmentManagement from './pages/admin/ExerciseAssignmentManagement';



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
    patient: '/patient/services',
    doctor: '/doctor/dashboard',
    admin: '/admin/dashboard',
  };

  return <Navigate to={routes[user.role] || '/login'} replace />;
}

function NotificationsSelector() {
  const { user } = useAuth();
  if (user?.role === 'admin') {
    return <AdminNotifications />;
  }
  return <CommonNotifications />;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <AuthProvider>
          <BrowserRouter>
            <Routes>
              {/* Public authentication routes */}
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              

              {/* Home redirect based on logged-in role */}
              <Route
                path="/"
                element={
                  <ProtectedRoute>
                    <HomeRedirect />
                  </ProtectedRoute>
                }
              />
              <Route path="/notifications" element={
                <ProtectedRoute>
                  <NotificationsSelector />
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
                <Route path="services" element={<ServiceSelection />} />

                <Route
                  path="laboratory"
                  element={<LaboratoryTests />}
                />

                <Route
                  path="appointments"
                  element={<PatientAppointments />}
                />

                <Route
                  path="laboratory/home-visit"
                  element={<HomeVisitLab />}
                />

                <Route
                  path="laboratory/clinic"
                  element={<ClinicLaboratoryVisit />}
                />

                <Route
                  path="laboratory/tests"
                  element={<LaboratoryTestSelection />}
                />

                <Route
                  path="laboratory/date-time"
                  element={<LaboratoryDateTime />}
                />

                <Route
                  path="laboratory/review"
                  element={<LaboratoryReview />}
                />

                <Route
                  path="laboratory/payment"
                  element={<LaboratoryPayment />}
                />

                <Route
                  path="laboratory/success"
                  element={<LaboratorySuccess />}
                />

                <Route
                  path="laboratory/bookings/:bookingId"
                  element={<LaboratoryBookingDetail />}
                />

                <Route path="dashboard" element={<PatientDashboard />} />
                <Route path="appointments" element={<PatientAppointments />} />
                <Route path="book" element={<BookAppointment />} />
                <Route path="history" element={<PatientHistory />} />
                <Route path="profile" element={<PatientProfile />} />
                <Route path="care-plan" element={<PatientCarePlan />} />
                <Route path="progress" element={<PatientProgress />} />
                <Route path="exercises" element={<PatientExercises />} />
                <Route path="reports" element={<PatientReports />} />
                <Route path="settings" element={<PatientSettings />} />
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
                <Route path="care-plans/:patientId" element={<CarePlanManagement />} />
                <Route path="exercises/:patientId" element={<ExerciseAssignmentManagement />} />
                <Route path="snapshot/:patientId" element={<PatientSnapshot />} />
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
                <Route path="care-plans/:patientId" element={<CarePlanManagement />} />
                <Route path="exercises/:patientId" element={<ExerciseAssignmentManagement />} />
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