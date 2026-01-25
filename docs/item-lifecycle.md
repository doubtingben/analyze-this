# Item Lifecycle

## New Item
An item is created when a user shares a media snippet. It is unanalyzed and has no next steps.

## Item Analysis
A worker process asynchronously analyzes the item. The item is marked as analyzed and has a next step and an overview.

During Analysis, the item has attributes extracted from the media snippet. These attributes are used to determine the next step.
Attributes include:
- date and time
- location (physical or virtual)
- principals (people)
- subject (what the media snippet is about)
- overview (summary of the media snippet)

The attributes are used to create embeddings for the item. The embeddings are used to find similar items and detect duplicates.
The attributes are also used to create the overview and should be used to search in the UIs.

### Next Steps
- Add to timeline
- Follow up
  - Is this a duplicate with another item?
  - Add context because I'm not sure what this is about 
  - Push (ask user again later, exponential backoff)
  - Processed (hide, add embeds, add to search index)
  - Soft Delete (hide and ignore)

## Item Processed
The item is hidden, has embeddings, and is added to the search index.

## Item Soft Deleted
The item is hidden and ignored.

## State Machine

```mermaid
stateDiagram-v2
    [*] --> New: User shares media

    New --> Analyzing: Worker picks up
    Analyzing --> Analyzed: Attributes extracted

    state Analyzed {
        [*] --> PendingAction
        note right of PendingAction
            Has: overview, attributes,
            embeddings, suggested next step
        end note
    }

    Analyzed --> Timeline: Add to timeline
    Analyzed --> FollowUp: Needs attention

    state FollowUp {
        [*] --> Triage
        Triage --> Duplicate: Merge with existing
        Triage --> NeedsContext: User adds info
        Triage --> Deferred: Push (exponential backoff)
        NeedsContext --> Triage: Re-evaluate
        Deferred --> Triage: Time elapsed
    }

    state Timeline {
        [*] --> Upcoming
        Upcoming --> Review: Event time passed (cron)
        note right of Review
            "How did it go?"
            Surfaced in daily conversation
        end note
    }

    FollowUp --> Processed: Resolved
    Timeline --> Processed: User reviews / no follow-up needed
    Analyzed --> Processed: No action needed
    Analyzed --> SoftDeleted: User dismisses

    state Processed {
        [*] --> Indexed
        note right of Indexed
            Hidden from main view
            Searchable via embeddings
        end note
    }

    state SoftDeleted {
        [*] --> Ignored
        note right of Ignored
            Hidden, not indexed
        end note
    }
```
