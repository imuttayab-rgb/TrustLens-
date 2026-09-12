'use client';

import { api } from '@/lib/api/client';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toApiError } from '@trustlens/api-client';

export interface ScoringWeight {
  signalCode: string;
  weight: number;
  hardCapOnFail: number | null;
  isEnabled: boolean;
}

export interface ScoringModel {
  id: string;
  version: string;
  name: string;
  description: string;
  isActive: boolean;
  algorithm: string;
  totalWeight: number;
  weights: ScoringWeight[];
  activatedAt: string | null;
}

const MODELS_KEY = ['admin', 'scoring-models'] as const;

export function useScoringModels() {
  return useQuery<ScoringModel[]>({
    queryKey: MODELS_KEY,
    queryFn: async () => {
      const result = await api.GET('/api/v1/admin/scoring-models');
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: ScoringModel[] }).data;
    },
  });
}

export function useActivateScoringModel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (modelId: string) => {
      const result = await api.POST('/api/v1/admin/scoring-models/{model_id}/activate', {
        params: { path: { model_id: modelId } },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: ScoringModel }).data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: MODELS_KEY }),
  });
}

export interface CreateScoringWeightInput {
  signalCode: string;
  weight: number;
  hardCapOnFail: number | null;
  isEnabled: boolean;
}

export interface CreateScoringModelInput {
  version: string;
  name: string;
  description: string;
  algorithm: string;
  weights: CreateScoringWeightInput[];
}

export function useCreateScoringModel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: CreateScoringModelInput) => {
      const result = await api.POST('/api/v1/admin/scoring-models', {
        body: {
          version: input.version,
          name: input.name,
          description: input.description,
          algorithm: input.algorithm,
          weights: input.weights.map((w) => ({
            signal_code: w.signalCode,
            weight: w.weight,
            hard_cap_on_fail: w.hardCapOnFail,
            is_enabled: w.isEnabled,
          })),
        },
      });
      if (result.error) throw toApiError(result.error);
      return (result.data as unknown as { data: ScoringModel }).data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: MODELS_KEY }),
  });
}
