import ontology from '../../../ontology/graph-ontology.json'

export const personalDataNodeTypes = ontology.personal_data_labels as readonly string[]
export const onsitNodeTypes = ontology.onsit_labels as readonly string[]
export const graphRelationshipTypes = ontology.relationships as readonly string[]
export const graphOntologyVersion = ontology.version

export function isPersonalDataNodeType(value: string): boolean {
  return personalDataNodeTypes.includes(value)
}
