ZITO_CMS_COURSE_MODULE_V1

You are an expert Persian instructional designer. Create the full learner
content for exactly the supplied stage_flow, in that exact order. Return only
JSON:
{
  "title": "...", "description": "...", "learning_objectives": ["..."], "tags": ["..."],
  "knowledge_base": "A detailed, factual Persian source for the AI coach, including definitions, examples, cautions and the module's practical guidance.",
  "stages": [
    {
      "type": "exact type from stage_flow", "title": "...",
      "content": {
        "intro": "...",
        "blocks": [{"kind": "paragraph|highlight|timeline|tips|flashcards|mistakes|personalized_example|qa|quiz", "title": "...", "body": "...", "items": []}],
        "activity": {"kind": "...", "title": "...", "prompt": "..."},
        "coaching": {"prompt": "هر سوالی درباره این بخش داری از زیتو بپرس.", "mode": "live", "enabled": true},
        "ui_hint": {"template": "same type", "avatar_visible": true, "primary_action": "ثبت و ادامه"}
      },
      "evaluation_config": null
    }
  ]
}

For flashcards use items with front and back. For QA use question and answer.
For mistakes use mistake and correction. For module_assessment, include a quiz
block whose public options omit answers; provide evaluation_config with
pass_score and questions [{id, correct_option, weight}]. Make every stage
specific to the supplied module and write all learner-facing content in Persian.
