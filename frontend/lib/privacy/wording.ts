export type ClaimBasis='observed'|'controller_assigned'|'technical_possibility'|'purpose_distance'|'unknown';
const prefixes:Record<ClaimBasis,string>={
  observed:'available export evidence indicates',controller_assigned:'appears controller-assigned',
  technical_possibility:'the combination could technically support',purpose_distance:'possible purpose drift',
  unknown:'no source evidence currently establishes',
};
const unsupported=['you are ','knows for certain','illegal','abusing','will survive deletion'];

export function guardedPrivacyStatement(statement:string,basis:ClaimBasis,directEvidence=false):string{
  const clean=statement.trim().replace(/\s+/g,' ');if(!clean)throw new Error('Presentation statement is required');
  if(!directEvidence&&unsupported.some(value=>clean.toLowerCase().includes(value)))throw new Error('Unsupported privacy wording');
  return `${prefixes[basis]}: ${clean[0].toLowerCase()}${clean.slice(1)}`;
}
