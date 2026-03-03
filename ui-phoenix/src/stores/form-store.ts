/**
 * Project Phoenix — Zustand Form Store
 * Centralizes all collection/report/SA/pipeline form state.
 * Persists to localStorage so users don't lose settings between sessions.
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { CollectionForm } from "@/types";

// ── Default form values (match original App.jsx) ────────────

export const defaultForm: CollectionForm = {
  countries: "Ethiopia",
  disaster_types: "epidemic/disease outbreak,flood,conflict emergency,drought",
  max_age_days: 30,
  limit: 10,
  limit_cycles: 20,
  limit_events: 30,
  country_min_events: 1,
  max_per_connector: 8,
  max_per_source: 4,
  report_template: "config/report_template.brief.json",
  use_llm: false,
  // Situation Analysis
  sa_title: "Situation Analysis",
  sa_event_name: "",
  sa_event_type: "",
  sa_period: "",
  sa_template: "config/report_template.situation_analysis.json",
  sa_limit_events: 80,
  sa_quality_gate: false,
  // Pipeline
  pipeline_report_title: "Disaster Intelligence Report",
  pipeline_sa_title: "Situation Analysis",
  pipeline_event_name: "",
  pipeline_event_type: "",
  pipeline_period: "",
};

// ── Store shape ─────────────────────────────────────────────

interface FormStoreState {
  form: CollectionForm;
  /** Update one or more form fields */
  setField: <K extends keyof CollectionForm>(key: K, value: CollectionForm[K]) => void;
  /** Merge partial form updates (for batch operations) */
  patchForm: (partial: Partial<CollectionForm>) => void;
  /** Reset form to defaults */
  resetForm: () => void;
}

// ── Store ───────────────────────────────────────────────────

export const useFormStore = create<FormStoreState>()(
  persist(
    (set) => ({
      form: { ...defaultForm },

      setField: (key, value) =>
        set((state) => ({
          form: { ...state.form, [key]: value },
        })),

      patchForm: (partial) =>
        set((state) => ({
          form: { ...state.form, ...partial },
        })),

      resetForm: () =>
        set(() => ({
          form: { ...defaultForm },
        })),
    }),
    {
      name: "phoenix-form-store",
      version: 1,
      migrate: (persisted, version) => {
        if (version === 0) {
          // v0 → v1: merge persisted values over current defaults
          return { form: { ...defaultForm, ...(persisted as { form: CollectionForm }).form } };
        }
        return persisted as FormStoreState;
      },
    }
  )
);
