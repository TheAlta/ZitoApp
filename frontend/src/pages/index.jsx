// Page registry: route name -> renderer. The shell wraps every non-public page.
import { Shell } from "../shell/Shell.jsx";
import { Certs, Profile } from "./Account.jsx";
import { Coach } from "./Coach.jsx";
import { CourseOverview } from "./CourseOverview.jsx";
import { Courses } from "./Courses.jsx";
import { FinalExam } from "./FinalExam.jsx";
import { Home } from "./Home.jsx";
import { Landing } from "./Landing.jsx";
import { Lesson } from "./Lesson.jsx";
import { Onboarding } from "./Onboarding.jsx";
import { AdminLogin, Certificate } from "./Public.jsx";
import { AdminHome } from "./admin/AdminHome.jsx";
import { Images } from "./admin/Images.jsx";
import { AdminNew, Studio } from "./admin/Studio.jsx";
import { Users } from "./admin/Users.jsx";

export const PAGES = {
  shell: Shell,
  landing: { render: () => <Landing /> },
  certificate: { render: (r) => <Certificate id={r.id} /> },
  "admin-login": { render: () => <AdminLogin /> },
  onboarding: { render: () => <Onboarding /> },
  home: { render: () => <Home /> },
  courses: { render: () => <Courses /> },
  course: { render: (r) => <CourseOverview slug={r.slug} /> },
  lesson: { render: () => <Lesson /> },
  coach: { render: () => <Coach />, wide: true },
  final: { render: () => <FinalExam /> },
  certs: { render: () => <Certs /> },
  profile: { render: () => <Profile /> },
  admin: { render: () => <AdminHome /> },
  "admin-new": { render: () => <AdminNew /> },
  "admin-studio": { render: (r) => <Studio courseId={r.courseId} version={r.version} tab={location.hash.slice(1) || r.tab} /> },
  "admin-images": { render: () => <Images /> },
  "admin-users": { render: (r) => <Users userId={r.userId} /> },
  "admin-preview": { render: (r) => <CourseOverview slug={r.slug} preview /> },
};
