import type { CapabilitySet, CharacterSummary, CharacterVariantSummary } from "../../client/types";
import { Card } from "../primitives/Card";
import { Inline } from "../primitives/Inline";
import { Section } from "../primitives/Section";
import { Stack } from "../primitives/Stack";

export interface CharacterIdentityCardProps {
  readonly character: CharacterSummary;
  readonly variant: CharacterVariantSummary | undefined;
  readonly capabilities: CapabilitySet | null;
}

/**
 * Character identity + package REFERENCE (never the full Accepted Package:
 * no claims, no biography/psychology/voice content -- only the same
 * identity fields `CharacterPackageRef` carries).
 */
export function CharacterIdentityCard({
  character,
  variant,
  capabilities,
}: CharacterIdentityCardProps) {
  const ref = character.packageRef;
  return (
    <Stack gap={4}>
      <Card raised>
        <Stack gap={2}>
          <h1 style={{ fontSize: "var(--clab-text-2xl)" }}>{character.displayName}</h1>
          <Inline gap={2}>
            <span className="clab-badge">{character.characterId}</span>
            {variant && <span className="clab-badge clab-badge--ok">{variant.displayName}</span>}
          </Inline>
        </Stack>
      </Card>

      {ref && (
        <Card>
          <Section title="Ссылка на пакет персонажа">
            <Stack gap={1}>
              <Inline gap={2}>
                <span className="clab-form-field__label">package_id</span>
                <span className="clab-hash">{ref.packageId}</span>
              </Inline>
              <Inline gap={2}>
                <span className="clab-form-field__label">package_version</span>
                <span>{ref.packageVersion}</span>
              </Inline>
              <Inline gap={2}>
                <span className="clab-form-field__label">acceptance_decision</span>
                <span className="clab-badge clab-badge--ok">{ref.acceptanceDecision}</span>
              </Inline>
              <Inline gap={2}>
                <span className="clab-form-field__label">candidate_status</span>
                <span className="clab-badge">{ref.candidateStatus}</span>
              </Inline>
              <Inline gap={2}>
                <span className="clab-form-field__label">source_hash</span>
                <span className="clab-hash">{ref.sourceHash}</span>
              </Inline>
            </Stack>
          </Section>
        </Card>
      )}

      <Card>
        <Section title="Возможности">
          <Inline gap={2}>
            {(capabilities?.capabilities ?? []).map((c) => (
              <span key={c} className="clab-badge">
                {c}
              </span>
            ))}
            {!capabilities && <span className="clab-form-field__label">загрузка…</span>}
          </Inline>
        </Section>
      </Card>
    </Stack>
  );
}
