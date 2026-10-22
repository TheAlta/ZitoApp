// Admin data shared across the CMS pages and the shell.
import { useMemo } from "react";
import { useCached } from "./cache.js";
import { fa } from "./format.js";

export const AK = {
  courses: "/api/admin/courses",
  users: "/api/admin/users",
  version: (courseId, version) => `/api/admin/courses/${courseId}/versions/${version}`,
  rag: (courseId, version) => `/api/admin/courses/${courseId}/versions/${version}/rag-status`,
  images: "/api/admin/course-images",
};

export const useAdminCourses = (enabled = true) => useCached(AK.courses, undefined, { enabled });
export const useAdminUsers = (enabled = true) => useCached(AK.users, undefined, { enabled });

// Recent CMS events reconstructed from timestamps the API exposes.
export function useAdminLog(enabled = true) {
  const courses = useAdminCourses(enabled);
  const users = useAdminUsers(enabled);
  return useMemo(() => {
    const log = [];
    for (const version of courses.data || []) {
      if (version.generated_at) log.push({ at: version.generated_at, kind: "generate", text: `پیش‌نویس «${version.course_title}» نسخه‌ی ${fa(version.version_number)} تولید شد` });
      if (version.published_at) log.push({ at: version.published_at, kind: "publish", text: `نسخه‌ی ${fa(version.version_number)} «${version.course_title}» منتشر شد` });
      if (version.version_number > 1 && version.created_at)
        log.push({ at: version.created_at, kind: "version", text: `نسخه‌ی ${fa(version.version_number)} «${version.course_title}» به‌صورت پیش‌نویس ساخته شد` });
    }
    for (const user of users.data || []) {
      if (user.created_at) log.push({ at: user.created_at, kind: "user", text: `کاربر تازه ثبت‌نام کرد: ${user.display_name}` });
      if (user.blocked_at) log.push({ at: user.blocked_at, kind: "user", text: `${user.display_name} مسدود شد` });
    }
    return log.sort((a, b) => new Date(b.at) - new Date(a.at)).slice(0, 20);
  }, [courses.data, users.data]);
}
