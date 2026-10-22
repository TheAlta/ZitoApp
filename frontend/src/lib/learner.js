// Learner data shared across pages: courses, my enrollments, current path and stage.
import { post } from "./api.js";
import { invalidate, load, useCached } from "./cache.js";

export const K = {
  courses: "/api/courses",
  overview: "/api/learning/overview",
  path: "/api/learning/enrollments/current",
  stage: (enrollmentId) => `/api/learning/enrollments/${enrollmentId}/stages/current`,
  coach: (enrollmentId) => `/api/learning/enrollments/${enrollmentId}/coach/messages`,
  final: (enrollmentId) => `/api/learning/enrollments/${enrollmentId}/final-exam`,
  course: (slug) => `/api/courses/slug/${encodeURIComponent(slug)}`,
};

export const useCourses = (enabled = true) => useCached(K.courses, undefined, { enabled });
export const useOverview = (enabled = true) => useCached(K.overview, undefined, { enabled });

// The current path 404s until the learner picks a course; that is a normal empty state.
export function useCurrentPath(enabled = true) {
  const result = useCached(K.path, undefined, { enabled });
  const none = result.error?.status === 404;
  return { ...result, data: none ? null : result.data, none, error: none ? null : result.error };
}

export function refreshLearning(enrollmentId) {
  invalidate(K.path, K.overview);
  if (enrollmentId) invalidate(K.stage(enrollmentId), K.final(enrollmentId));
}

// Enrolling an existing course just makes it the current one again.
export async function selectCourse(courseId) {
  const enrollment = await post(`/api/courses/${courseId}/enroll`);
  refreshLearning(enrollment.id);
  await load(K.path, undefined, { force: true }).catch(() => {});
  return enrollment;
}

export const STAGE_TITLES = {
  learning_path: "مسیر یادگیری",
  lesson_summary: "خلاصه درس",
  flashcards: "فلش‌کارت‌ها",
  golden_tips: "نکات طلایی",
  common_mistakes: "اشتباهات رایج",
  personalized_work_example: "مثال در مسیر شغلی تو",
  module_assessment: "آزمونک سرفصل",
  module_completion: "پایان سرفصل",
};
export const STAGE_KINDS = Object.keys(STAGE_TITLES);

export const learnerStatus = (status) =>
  status === "awaiting_final_exam" || status === "awaiting_final" ? "awaiting_final" : status === "completed" ? "completed" : "learning";

// Reads the API learning path into what the screens need: where the learner is and how far along.
export function pathInfo(path) {
  if (!path) return null;
  const stages = path.stages || [];
  const current = stages.find((s) => s.is_current) || null;
  const modules = path.modules || [];
  const moduleIndex = current ? Math.max(0, modules.findIndex((m) => m.module_id === current.module_id)) : modules.length - 1;
  const module = modules[moduleIndex] || null;
  const moduleStages = module ? stages.filter((s) => s.module_id === module.module_id) : [];
  const stageIndex = current ? Math.max(0, moduleStages.findIndex((s) => s.stage_number === current.stage_number)) : moduleStages.length;
  const total = path.total_stage_count || stages.length;
  const completed = path.completed_stage_count ?? stages.filter((s) => s.status === "completed").length;
  return {
    status: learnerStatus(path.status),
    current,
    module,
    moduleIndex,
    moduleStages,
    stageIndex,
    moduleCount: path.module_count || modules.length,
    completed,
    total,
    percent: total ? (completed / total) * 100 : 0,
  };
}
