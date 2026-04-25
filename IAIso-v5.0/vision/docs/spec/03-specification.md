Section 03: Component Structure

IAIso v5.0 is modular and versioned. Every artifact—be it a layer definition, an invariant, or a prompt template—is treated as a Component validated against a strict JSON schema.

1. Component Anatomy

Every component in the /components/ or /templates/ directory must include the following mandatory metadata to be considered valid by the iaiso-validate.py suite.

+----------------+-------------------------------------------------------------------------------+
| Attribute      | Description                                                                   |
+================+===============================================================================+
| ID | Unique, versioned identifier (e.g., inv-pressure-track-v5-0).               |
+----------------+-------------------------------------------------------------------------------+
| Type | Classification: layer, invariant, template, or integration.           |
+----------------+-------------------------------------------------------------------------------+
| ConsentScope| The cryptographically signed authorization tag required to invoke this.      |
+----------------+-------------------------------------------------------------------------------+
| Invariants | A list of local invariants that must hold for this component to remain active.|
+----------------+-------------------------------------------------------------------------------+
| Status | Deployment state: locked (production) or open (testing).                  |
+----------------+-------------------------------------------------------------------------------+

2. The Component Registry

To maintain the "Mechanical Containment" integrity, all components are registered in a central manifest. This allows the system to calculate the total "Data Reach" of an agent by summing the authorized scopes across all active components.

3. Schema Enforcement

Components are validated using the components/component-schema.json. Any artifact that lacks a valid ConsentScope or attempts to reference a non-existent Layer ID is automatically quarantined by the Layer 0 physical boundary.

Powered by Smarttasks — "Build with vision, count on precision."