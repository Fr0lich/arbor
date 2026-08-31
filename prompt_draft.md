Hello AI Agent!

I need you to implement a specific behavior for the mobile companion app in Arbor. When the user clicks the hardware/browser "back" button on their phone while inside the mobile companion app, I want it to behave intelligently based on the current view, instead of simply taking the user all the way back to the PIN code login screen.

Here are the specific requirements:

1. **Detail View:** When the user is on the "Detail View" (viewing a specific specimen) and clicks the hardware back button, it should act as if they tapped the top-left UI back button (which calls `showListView()`). It must take them back to the List View.
2. **List View:** If the user is on the main "List View" (the primary list of items) and they click the hardware back button, a soft popup (modal/overlay) should appear in the middle of the screen with the text: "do you want to leave the database? (you might need to resync)". If they confirm, they can proceed back; if they cancel, they stay on the List View.
3. **Implementation Details:**
   - You must use the HTML5 History API (`window.history.pushState` and `window.history.replaceState`) and listen for the `popstate` event.
   - You should update the existing `showListView()` and `showDetailView()` (or `loadSpecimen()`) functions to manage the history state.
   - For example, when `showDetailView()` is called, push a state like `{ view: 'detail' }`. When `showListView()` is called, push or replace state as appropriate.
   - On the `popstate` event listener, read the state and execute the corresponding view function, or show the confirmation popup if they try to leave the List View.

4. **Project Constraints:**
   - **Crucial Rule:** The frontend of the mobile application lives *entirely* inside the `INDEX_TEMPLATE` string variable within the `backend/mobile_server.py` file.
   - **Do NOT create, use, or modify any external HTML files** (like `mobile_frontend.html`). Any changes to HTML, JS, or CSS must be done directly inside the `INDEX_TEMPLATE` string in `backend/mobile_server.py`.
   - Ensure you follow the project's Tailwind CSS styling for the soft popup modal (e.g., matching other modals like `connectionModal`).

Please provide the updated `INDEX_TEMPLATE` code, explicitly explaining which sections of `backend/mobile_server.py` are being modified to implement this new routing logic.
