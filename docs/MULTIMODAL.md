# Multimodal Architecture

Status: Step 13 foundation.

## Scope

This layer prepares the project for image and audio documents.

Current scope:

- image/audio modality detection;
- stable asset metadata;
- metadata-only document records;
- planned OCR/image-description/image-embedding derivatives;
- planned audio-transcription/audio-embedding derivatives;
- multimodal source visibility in output validation.

Out of scope for this step:

- no AI model calls;
- no OCR execution;
- no image description generation;
- no audio transcription;
- no image/audio embeddings;
- no corpus/document mutation.

## Historian Note

The project deliberately does not process real media yet.

Step 13 only creates contracts and safe placeholders so future media models can
be trained or connected later. Any future agent must preserve this distinction:
metadata contracts are implemented, but multimodal intelligence is deferred.

## Data Model

`AssetRecord` stores:

- `asset_id`;
- `universe_id`;
- `source_path`;
- `modality`;
- `media_type`;
- `sha256`;
- `size_bytes`;
- processing status;
- derivative metadata.

`MediaDerivative` stores planned or produced outputs:

- `ocr_text`;
- `image_description`;
- `image_embedding`;
- `audio_transcript`;
- `audio_embedding`;
- future video/PDF derivatives.

`DocumentRecord.media` can reference the asset and planned derivatives.

## Current Behavior

Image/audio ingestion is metadata-only.

It creates:

- an empty `raw_content`;
- an empty `clean_content`;
- `metadata.processing_mode = "metadata_only"`;
- `metadata.ai_models_used = []`;
- planned derivative records.

Validation reports expose:

- source modality counts;
- non-text source references;
- whether extracted text exists.

## Future Order

1. Add OCR behind an explicit optional dependency.
2. Add image description behind an explicit provider/local model interface.
3. Add image embeddings.
4. Add audio transcription.
5. Add audio embeddings.
6. Add video only after image/audio are stable.
