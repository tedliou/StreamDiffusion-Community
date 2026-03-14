from typing import Any


def resolve_clip_image_processor_class(transformers_module: Any) -> type:
    clip_image_processor = getattr(transformers_module, "CLIPImageProcessor", None)
    if clip_image_processor is not None:
        return clip_image_processor

    clip_feature_extractor = getattr(transformers_module, "CLIPFeatureExtractor", None)
    if clip_feature_extractor is not None:
        return clip_feature_extractor

    raise ImportError(
        "transformers does not expose CLIPImageProcessor or CLIPFeatureExtractor"
    )
