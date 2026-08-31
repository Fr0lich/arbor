1. **Understand the Goal**: The user wants a companion prompt to follow the provided prompt, focusing on decoupling and reducing the size of the massive `ui/main_window.py` (which is ~10,000 lines).
2. **Draft the Prompt**: I will write a comprehensive prompt tailored to safely and efficiently refactoring `ui/main_window.py`. The prompt will emphasize a component-based approach (extracting UI panels one by one), using the EventBus (`app_bus`) for communication, and maintaining strict safety protocols to avoid breaking the fragile codebase.
3. **Review against Requirements**:
   - Matches the structure of the provided prompt (Context, Prior Work, Execution Goals & Strategies, Crucial Rules & Pitfalls).
   - Provides clear, actionable steps for a subsequent AI agent.
   - Focuses on safely reducing the size of `main_window.py`.
4. **Deliver to User**: I will present the drafted prompt to the user using `message_user`.
