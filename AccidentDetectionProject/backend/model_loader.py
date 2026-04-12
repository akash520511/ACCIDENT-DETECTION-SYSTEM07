import os
import torch
import torch.nn as nn
from typing import Optional, Dict
import json
from loguru import logger

class ModelLoader:
    """Utility class for loading and managing ML models"""
    
    def __init__(self, model_dir: str = "models"):
        self.model_dir = model_dir
        self.models: Dict[str, nn.Module] = {}
        self.model_configs: Dict = {}
        
        # Create model directory if it doesn't exist
        os.makedirs(model_dir, exist_ok=True)
        
    def load_model(self, model_name: str, model_class: nn.Module, 
                   weights_path: Optional[str] = None) -> Optional[nn.Module]:
        """Load a model with optional weights"""
        try:
            model = model_class()
            
            if weights_path and os.path.exists(weights_path):
                state_dict = torch.load(weights_path, map_location='cpu')
                model.load_state_dict(state_dict, strict=False)
                logger.info(f"Loaded weights for {model_name} from {weights_path}")
            
            self.models[model_name] = model
            return model
            
        except Exception as e:
            logger.error(f"Error loading model {model_name}: {e}")
            return None
    
    def save_model(self, model_name: str, model: nn.Module, 
                   weights_path: str, config: Optional[Dict] = None):
        """Save model weights and configuration"""
        try:
            # Save weights
            torch.save(model.state_dict(), weights_path)
            
            # Save config
            if config:
                config_path = weights_path.replace('.pth', '_config.json')
                with open(config_path, 'w') as f:
                    json.dump(config, f, indent=2)
            
            logger.info(f"Saved model {model_name} to {weights_path}")
            
        except Exception as e:
            logger.error(f"Error saving model {model_name}: {e}")
    
    def get_model(self, model_name: str) -> Optional[nn.Module]:
        """Get loaded model by name"""
        return self.models.get(model_name)
    
    def unload_model(self, model_name: str):
        """Unload model to free memory"""
        if model_name in self.models:
            del self.models[model_name]
            logger.info(f"Unloaded model {model_name}")
    
    def list_models(self) -> list:
        """List all loaded models"""
        return list(self.models.keys())
    
    def get_model_info(self, model_name: str) -> Dict:
        """Get information about a model"""
        model = self.models.get(model_name)
        if not model:
            return {}
        
        total_params = sum(p.numel() for p in model.parameters())
        trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
        
        return {
            'name': model_name,
            'type': model.__class__.__name__,
            'total_parameters': total_params,
            'trainable_parameters': trainable_params,
            'device': next(model.parameters()).device.type
        }

# Example usage
if __name__ == "__main__":
    loader = ModelLoader()
    # loader.load_model("accident_detector", AccidentDetector, "models/best/model_weights.pth")
    print("Model loader ready")
