/**
 * Neutral portrait placeholder (data-URI SVG). NOT a final visual asset and NOT
 * a character reference — it only fills the persistent portrait slot until a
 * Companion-safe portrait asset is bound (PORTRAIT_ASSET_BINDING_PENDING).
 *
 * Arbitrary portrait upload is intentionally NOT available: the Attachment
 * Security Gateway is not implemented yet.
 */

const SVG = `<svg xmlns='http://www.w3.org/2000/svg' width='320' height='420'>
  <rect width='100%' height='100%' fill='#191b20'/>
  <circle cx='160' cy='150' r='64' fill='#2b2e35'/>
  <rect x='72' y='230' width='176' height='150' rx='24' fill='#2b2e35'/>
  <text x='50%' y='400' fill='#6b7079' font-family='sans-serif' font-size='16' text-anchor='middle'>портрет</text>
</svg>`;

export const PORTRAIT_PLACEHOLDER_DATA_URI =
  "data:image/svg+xml;utf8," + encodeURIComponent(SVG);
