/**
 * Project Phoenix — Phase 4 Preset Manager Modal
 * Save, load, and delete workbench profile presets.
 * Uses dialog UI with profile listing and save-new form.
 */

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { useWorkbenchProfiles } from "@/hooks/use-queries";
import {
  useSaveWorkbenchProfile,
  useDeleteWorkbenchProfile,
} from "@/hooks/use-mutations";
import { useFormStore } from "@/stores/form-store";
import { toast } from "sonner";
import {
  Save,
  Trash2,
  Download,
  Loader2,
  FolderOpen,
} from "lucide-react";
import { useState, useCallback } from "react";
import type { CollectionForm } from "@/types";

interface PresetManagerModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentProfile: Record<string, unknown>;
}

export function PresetManagerModal({
  open,
  onOpenChange,
  currentProfile,
}: PresetManagerModalProps) {
  const { data: profileStore, isLoading } = useWorkbenchProfiles();
  const saveProfile = useSaveWorkbenchProfile();
  const deleteProfile = useDeleteWorkbenchProfile();
  const patchForm = useFormStore((s) => s.patchForm);

  const [newName, setNewName] = useState("");

  const presets = profileStore?.presets ?? {};
  const presetNames = Object.keys(presets);

  const handleSave = useCallback(() => {
    const trimmed = newName.trim();
    if (!trimmed) {
      toast.error("Please enter a preset name");
      return;
    }
    saveProfile.mutate(
      { name: trimmed, profile: currentProfile },
      {
        onSuccess: () => {
          toast.success(`Preset "${trimmed}" saved`);
          setNewName("");
        },
        onError: (err) => {
          toast.error(`Failed to save: ${err.message}`);
        },
      },
    );
  }, [newName, currentProfile, saveProfile]);

  const handleLoad = useCallback(
    (name: string) => {
      const profile = presets[name];
      if (!profile) return;
      // Merge preset values into form store
      const patch: Record<string, unknown> = {};
      for (const [key, value] of Object.entries(profile)) {
        patch[key] = value;
      }
      patchForm(patch as Partial<CollectionForm>);
      toast.success(`Preset "${name}" loaded`);
      onOpenChange(false);
    },
    [presets, patchForm, onOpenChange],
  );

  const handleDelete = useCallback(
    (name: string) => {
      deleteProfile.mutate(name, {
        onSuccess: () => {
          toast.success(`Preset "${name}" deleted`);
        },
        onError: (err) => {
          toast.error(`Failed to delete: ${err.message}`);
        },
      });
    },
    [deleteProfile],
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FolderOpen className="h-5 w-5 text-primary" />
            Workbench Presets
          </DialogTitle>
          <DialogDescription>
            Save the current workbench configuration as a preset, or load an existing one.
          </DialogDescription>
        </DialogHeader>

        {/* Save new preset */}
        <div className="space-y-3">
          <Label htmlFor="preset-name">Save Current as Preset</Label>
          <div className="flex gap-2">
            <Input
              id="preset-name"
              placeholder="Enter preset name…"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleSave();
              }}
            />
            <Button
              onClick={handleSave}
              disabled={saveProfile.isPending || !newName.trim()}
              size="sm"
              className="shrink-0"
            >
              {saveProfile.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Save className="h-4 w-4 mr-1.5" />
              )}
              Save
            </Button>
          </div>
        </div>

        {/* Existing presets */}
        <div className="space-y-2 mt-4">
          <Label>Saved Presets</Label>
          {isLoading && (
            <p className="text-sm text-muted-foreground py-2">Loading…</p>
          )}
          {!isLoading && presetNames.length === 0 && (
            <p className="text-sm text-muted-foreground py-2">
              No presets saved yet. Save one above to get started.
            </p>
          )}
          {presetNames.length > 0 && (
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {presetNames.map((name) => {
                const profile = presets[name];
                const countries = String(profile?.countries ?? "—");
                return (
                  <div
                    key={name}
                    className="flex items-center justify-between rounded-lg bg-muted/20 border border-border px-4 py-3"
                  >
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-foreground truncate">
                        {name}
                      </div>
                      <div className="text-xs text-muted-foreground truncate">
                        {countries}
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleLoad(name)}
                        title="Load preset"
                      >
                        <Download className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDelete(name)}
                        disabled={deleteProfile.isPending}
                        title="Delete preset"
                        className="text-destructive hover:text-destructive"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Last used profile */}
        {profileStore?.last_profile && (
          <div className="mt-2">
            <Badge variant="outline" className="text-xs">
              Last profile: {String(profileStore.last_profile.countries ?? "—")}
            </Badge>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
