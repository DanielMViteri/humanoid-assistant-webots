# Scope Reset

## New Direction

SwarmSense is now scoped as a modular ROS2 robot assistant where each major ability is implemented as a separate Python ROS2 node.

The goal is not to build every AI capability deeply in the first sprint. The goal is to prove a working node-based architecture, then add abilities in priority order.

## MVP Outcome

The MVP should demonstrate this flow:

```text
User input -> NLP processing -> robot response -> session/status storage -> dashboard/status output
```

Robot telemetry remains part of the system, but it is now one ability node rather than the entire product.

## Scope Rules

- Keep each ability isolated as a node.
- Use OpenAI API for MVP NLP instead of building custom NLP models.
- Keep computer vision features as stretch until the core conversation loop works.
- Use simple storage first, then upgrade only if needed.
- Treat Kafka, advanced Webots behavior, and heavy ML models as stretch integrations.

## MVP Features

1. Text or voice input intake
2. OpenAI-powered NLP response
3. Mood or intent extraction from user text
4. Text-to-speech response
5. Session history logging
6. Simple wellbeing/status score
7. Dashboard/status display
8. Robot/system telemetry publishing

## Stretch Features

1. Facial emotion recognition
2. Person detection
3. Gesture/body cue recognition
4. Long-term vector memory
5. Telegram or external alerting
6. Kafka streaming layer
7. Webots multi-robot telemetry integration
