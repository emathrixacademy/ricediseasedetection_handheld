"""Image preprocessing and augmentation transforms.

Prefers albumentations when available; otherwise falls back to torchvision.
Heavy imports are guarded so this module imports without those libs present.
"""

# ImageNet normalization constants (RGB).
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


def _build_albumentations(image_size, train):
    import albumentations as A
    from albumentations.pytorch import ToTensorV2

    if train:
        return A.Compose([
            A.Resize(image_size, image_size),
            A.HorizontalFlip(p=0.5),
            A.VerticalFlip(p=0.2),
            A.RandomBrightnessContrast(p=0.3),
            A.ShiftScaleRotate(shift_limit=0.05, scale_limit=0.1,
                               rotate_limit=20, p=0.4),
            A.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
            ToTensorV2(),
        ])
    return A.Compose([
        A.Resize(image_size, image_size),
        A.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        ToTensorV2(),
    ])


def _build_torchvision(image_size, train):
    from torchvision import transforms

    if train:
        return transforms.Compose([
            transforms.Resize((image_size, image_size)),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.RandomVerticalFlip(p=0.2),
            transforms.ColorJitter(brightness=0.2, contrast=0.2),
            transforms.RandomRotation(20),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ])
    return transforms.Compose([
        transforms.Resize((image_size, image_size)),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])


def get_transforms(image_size=224, train=True, prefer_albumentations=True):
    """Return an augmentation/preprocess transform.

    Falls back to torchvision if albumentations is not installed.
    Note: albumentations transforms expect a numpy array under the
    ``image`` keyword; torchvision transforms expect a PIL image.
    """
    if prefer_albumentations:
        try:
            return _build_albumentations(image_size, train)
        except ImportError:
            pass
    return _build_torchvision(image_size, train)


if __name__ == "__main__":
    t = get_transforms(224, train=True)
    print("Built transform:", type(t).__name__)
