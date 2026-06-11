import type {
  HelmData,
  OnchainArtifact,
  RegimeArtifact,
  ValidationArtifact,
} from './types';

// Resolve fetch URL against the deployed base path. For a static export served
// from a subdirectory the relative path keeps things portable.
function dataUrl(name: string): string {
  return `data/${name}`;
}

async function fetchJson<T>(name: string): Promise<T> {
  const res = await fetch(dataUrl(name), { cache: 'no-store' });
  if (!res.ok) {
    throw new Error(`Failed to load ${name}: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

export async function loadHelmData(): Promise<HelmData> {
  const [regime, onchain, validation] = await Promise.all([
    fetchJson<RegimeArtifact>('regime_artifact.json'),
    fetchJson<OnchainArtifact>('onchain_validation_artifact.json'),
    fetchJson<ValidationArtifact>('validation_artifact.json'),
  ]);
  return { regime, onchain, validation };
}
