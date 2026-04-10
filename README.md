![Logo for the Ardent Forge project](./assets/AF.svg)

# Ardent Forge

This is my agentic platform. There are many like it, but this one is mine.

I run Ardent Forge on a small server at home to handle development tasks, personal notetaking systems, and overall handle my relevant work that can be done with the assistance of LLMs.

The system is based around a leader agent: `Ardent Forge`. This agent is a coordinator for many sub-agents. A core loop pulls in tasks from external systems (just Linear today) and stores them in a SQLite database. 

Tasks are executed with the following workflow:

```
Queued -> Triaging -> Executing -> Verifying -> Delivering -> Completed
    |                   ^
    |___________________|

Each state can transition to the "Failed" state where it may or may not be requeued.
```

To add a new function to this system, an agent needs to be built which implements each of these stages. 

The system checkpoints state frequenly to a local SQLite database. This allows safe restarts and resumability of tasks.

