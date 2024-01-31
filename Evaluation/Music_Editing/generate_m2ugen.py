import sys

sys.path.append('../../M2UGen')

import json
from tqdm import tqdm
from llama.m2ugen import M2UGen
import llama
import os
from pydub import AudioSegment
import scipy
import torch
from PIL import Image
import torchvision.transforms as transforms
import argparse
from pathlib import Path
import torchaudio

parser = argparse.ArgumentParser()
parser.add_argument(
    "--model", default="./ckpts/checkpoint.pth", type=str,
    help="Name of or path to M2UGen pretrained checkpoint",
)
parser.add_argument(
    "--llama_type", default="7B", type=str,
    help="Type of llama original weight",
)
parser.add_argument(
    "--llama_dir", default="/path/to/llama", type=str,
    help="Path to LLaMA pretrained checkpoint",
)
parser.add_argument(
    "--mert_path", default="m-a-p/MERT-v1-330M", type=str,
    help="Path to MERT pretrained checkpoint",
)
parser.add_argument(
    "--vit_path", default="m-a-p/MERT-v1-330M", type=str,
    help="Path to ViT pretrained checkpoint",
)
parser.add_argument(
    "--vivit_path", default="m-a-p/MERT-v1-330M", type=str,
    help="Path to ViViT pretrained checkpoint",
)
parser.add_argument(
    "--knn_dir", default="./ckpts", type=str,
    help="Path to directory with KNN Index",
)
parser.add_argument(
    '--music_decoder', default="musicgen", type=str,
    help='Decoder to use musicgen/audioldm2')

parser.add_argument(
    '--music_decoder_path', default="facebook/musicgen-medium", type=str,
    help='Path to decoder to use musicgen/audioldm2')

args = parser.parse_args()

llama_type = args.llama_type
llama_ckpt_dir = os.path.join(args.llama_dir, llama_type)
llama_tokenzier_path = args.llama_dir
model = M2UGen(llama_ckpt_dir, llama_tokenzier_path, args, knn=False, stage=3, load_llama=False)

print("Loading Model Checkpoint")
checkpoint = torch.load(args.model, map_location='cpu')

new_ckpt = {}
for key, value in checkpoint['model'].items():
    key = key.replace("module.", "")
    new_ckpt[key] = value

load_result = model.load_state_dict(new_ckpt, strict=True)
assert len(load_result.unexpected_keys) == 0, f"Unexpected keys: {load_result.unexpected_keys}"
model.eval()
model.to("cuda")

source_files = [str(x).split("/")[-1] for x in Path("./results/source").glob("*.wav")]

def generate(prompt, audio_file, length_in_sec=10, top_p=0.8, temperature=0.6):
    sample_rate = 24000
    waveform, sr = torchaudio.load(audio_file)
    if sample_rate != sr:
        waveform = torchaudio.functional.resample(waveform, orig_freq=sr, new_freq=sample_rate)
    audio = torch.mean(waveform, 0)
    prompts = [llama.format_prompt(prompt)]
    prompts = [model.tokenizer(x).input_ids for x in prompts]
    image, video = None, None
    response = model.generate(prompts, audio, image, video, 512,
                              temperature=temperature, top_p=top_p, audio_length_in_s=length_in_sec)
    return response[-1]['aud']


if not os.path.exists("./results/m2ugen"):
    os.makedirs("./results/m2ugen")

data = {}
for file in source_files:
    data[file] = " ".join(file.split("_")[:-1])

for music, instruction in data.keys():
    audioSegment = AudioSegment.from_wav(os.path.join("./results/source/", music))
    audio = generate(instruction, f"./results/source/{music}", length_in_sec=audioSegment.duration_seconds)
    scipy.io.wavfile.write(f"./results/m2ugen/{music.replace('.mp3', '.wav')}", rate=16000, data=audio)
