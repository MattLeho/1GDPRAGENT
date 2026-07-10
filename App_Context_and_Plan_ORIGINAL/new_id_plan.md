
### **Document 2: `NEW_ID_PLAN.md`**
*Create this file. It defines the UX for the Identity Form.*

```markdown
# NEW REQUEST PAGE: IDENTITY & ACCOUNT WIZARD

## 1. Design Philosophy
The "Add Identity" panel is no longer a flat form. It is a **Relationship Builder**.
It must visually show how the selected Name, Email, and Account link together.

## 2. User Interface Structure

### Zone A: The Persona Selector (The Context)
*   **Question:** "Who are you acting as?"
*   **UI:** Horizontal scrolling cards or bubbles.
    *   [ 🏢 Professional ] [ 🎮 Gamer ] [ 👻 Anonymous ] [ + New ]
*   **Action:** Selecting "Gamer" auto-filters the lists below.

### Zone B: The Attribute Mixer (The Details)
*   **Layout:** Three columns with "Connectors" (lines) drawn between them.
    1.  **Name:** Dropdown of your known aliases (e.g., "John D.", "J. Doe").
    2.  **Email:** Dropdown of emails associated with the selected Persona.
    3.  **Phone:** (Optional) Linked number.
*   **Interaction:** Changing the Persona updates these defaults, but the user can override specific fields for this specific request.

### Zone C: The Account Specifics (The Target)
*   **Context:** "We are requesting [Company Name]".
*   **Fields:**
    *   **Username:** (Text Input)
    *   **Specific ID:** (e.g., "Steam ID", "Amazon Customer #")
*   **Linkage:** A checkbox "Save this account configuration to my Graph?"

## 3. CRUD Functionality
- **Create:** "Add New Identity" button opens a modal to define a new Name/Email node.
- **Edit:** Clicking the "Edit" pencil on an attribute node allows renaming or re-linking.
- **Delete:** "Forget this Identity" removes the node and creates "Orphan" warnings for linked accounts.

## 4. The "Mini-Map" Preview
At the bottom of the panel, a small SVG visualization shows the link being created:
`[Me] --(Gamer)--> [john.g@mail] --(Login)--> [Steam]`