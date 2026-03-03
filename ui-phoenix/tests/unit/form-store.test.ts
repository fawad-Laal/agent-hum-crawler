/**
 * Phase 2 — Form Store Tests
 * Verifies Zustand form store: defaults, setField, patchForm, resetForm.
 */

import { describe, it, expect, beforeEach } from "vitest";
import { useFormStore, defaultForm } from "@/stores/form-store";

describe("formStore", () => {
  beforeEach(() => {
    // Reset store to defaults before each test
    useFormStore.getState().resetForm();
  });

  it("initializes with default values", () => {
    const { form } = useFormStore.getState();
    expect(form.countries).toBe("Ethiopia");
    expect(form.max_age_days).toBe(30);
    expect(form.limit).toBe(10);
    expect(form.use_llm).toBe(false);
    expect(form.sa_quality_gate).toBe(false);
    expect(form.report_template).toBe("config/report_template.brief.json");
  });

  it("setField updates a single field", () => {
    useFormStore.getState().setField("countries", "Madagascar");
    expect(useFormStore.getState().form.countries).toBe("Madagascar");
    // Other fields untouched
    expect(useFormStore.getState().form.max_age_days).toBe(30);
  });

  it("setField updates boolean field", () => {
    useFormStore.getState().setField("use_llm", true);
    expect(useFormStore.getState().form.use_llm).toBe(true);
  });

  it("setField updates numeric field", () => {
    useFormStore.getState().setField("limit", 50);
    expect(useFormStore.getState().form.limit).toBe(50);
  });

  it("patchForm merges multiple fields at once", () => {
    useFormStore.getState().patchForm({
      countries: "Mozambique",
      disaster_types: "cyclone/storm,flood",
      max_age_days: 14,
    });
    const { form } = useFormStore.getState();
    expect(form.countries).toBe("Mozambique");
    expect(form.disaster_types).toBe("cyclone/storm,flood");
    expect(form.max_age_days).toBe(14);
    // Other fields untouched
    expect(form.limit).toBe(10);
  });

  it("resetForm restores all defaults", () => {
    useFormStore.getState().setField("countries", "Kenya");
    useFormStore.getState().setField("limit", 99);
    useFormStore.getState().resetForm();
    const { form } = useFormStore.getState();
    expect(form.countries).toBe(defaultForm.countries);
    expect(form.limit).toBe(defaultForm.limit);
  });

  it("SA fields have correct defaults", () => {
    const { form } = useFormStore.getState();
    expect(form.sa_title).toBe("Situation Analysis");
    expect(form.sa_template).toBe("config/report_template.situation_analysis.json");
    expect(form.sa_limit_events).toBe(80);
  });

  it("pipeline fields have correct defaults", () => {
    const { form } = useFormStore.getState();
    expect(form.pipeline_report_title).toBe("Disaster Intelligence Report");
    expect(form.pipeline_sa_title).toBe("Situation Analysis");
    expect(form.pipeline_event_name).toBe("");
  });
});
