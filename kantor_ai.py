import os, json, subprocess, time
from google import genai

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

print("1. [TIM RISET] Membaca syarat campaign harian...")
with open("syarat_harian.txt", "r") as f:
    syarat = f.read()

link_yt = [line.split(": ", 1)[1].strip() for line in syarat.splitlines() if line.startswith("LINK_YOUTUBE:")][0]

print(f"2. [TIM PRODUKSI] Mengunduh video materi dari {link_yt}...")
os.makedirs("output_klip", exist_ok=True)
if os.path.exists("source_video.mp4"):
    os.remove("source_video.mp4")
subprocess.run(["yt-dlp", "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4", "-o", "source_video.mp4", link_yt], check=True)

print("3. [TIM QC & ANALISIS] Mengunggah video ke Gemini AI untuk seleksi & QC Konten.com...")
video_file = client.files.upload(file="source_video.mp4")
while video_file.state.name == "PROCESSING":
    time.sleep(5)
    video_file = client.files.get(name=video_file.name)

prompt = f"""
Kamu adalah Tim Riset, Produksi, dan Quality Control (QC) Kantor AI Clipper untuk platform Konten.com.
Baca dengan teliti syarat campaign harian berikut:
{syarat}

Tugasmu secara berurutan:
1. RISET & SELEKSI: Temukan maksimal 3 momen paling potensial viral dari video ini (memiliki hook kuat di 3 detik pertama, alur pembicaraan utuh, dan sesuai TOPIK_DICARI).
2. QUALITY CONTROL (QC): Pastikan setiap segmen yang dipilih durasinya wajib berada di antara DURASI_MINIMAL dan DURASI_MAKSIMAL, serta 100% bebas dari LARANGAN. Tolak dan jangan masukkan segmen yang melanggar syarat.
3. COPYWRITING INSTAGRAM: Untuk setiap segmen yang LOLOS QC, tulis caption Instagram Reels yang memancing interaksi (komentar/share) dan wajib mencantumkan MENTION_WAJIB serta HASHTAG_WAJIB.

Berikan jawaban HANYA dalam format JSON array valid tanpa teks pembuka atau penutup:
[
  {{
    "judul": "nama_file_singkat_tanpa_spasi",
    "mulai": "00:01:15",
    "selesai": "00:01:50",
    "alasan_lolos_qc": "Penjelasan singkat kenapa lolos syarat campaign",
    "caption_ig": "Teks hook menarik + mention wajib + hashtag wajib"
  }}
]
"""

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=[video_file, prompt]
)

raw_json = response.text.strip().removeprefix("```json").removesuffix("```").strip()
klip_list = json.loads(raw_json)

for idx, klip in enumerate(klip_list, 1):
    raw_cut = f"temp_{idx}.mp4"
    out_mp4 = f"output_klip/{idx}_{klip['judul']}.mp4"
    out_txt = f"output_klip/{idx}_{klip['judul']}_caption.txt"
    
    print(f"4. [EDITING KLIP {idx}] {klip['mulai']} -> {klip['selesai']} | QC: {klip['alasan_lolos_qc']}")
    subprocess.run([
        "ffmpeg", "-y", "-i", "source_video.mp4",
        "-ss", klip["mulai"], "-to", klip["selesai"],
        "-vf", "crop=ih*(9/16):ih,scale=1080:1920",
        "-c:v", "libx264", "-c:a", "aac", raw_cut
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print(f"   [SUBTITLE KLIP {idx}] Memasang subtitle otomatis...")
    subprocess.run(["whisper", raw_cut, "--model", "base", "--language", "Indonesian", "--output_format", "srt"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    srt_file = f"temp_{idx}.srt"
    if os.path.exists(srt_file):
        subprocess.run([
            "ffmpeg", "-y", "-i", raw_cut,
            "-vf", f"subtitles={srt_file}:force_style='FontSize=14,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,Alignment=2,MarginV=50'",
            "-c:a", "copy", out_mp4
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.remove(srt_file)
    else:
        os.rename(raw_cut, out_mp4)

    if os.path.exists(raw_cut):
        os.remove(raw_cut)

    with open(out_txt, "w") as cf:
        cf.write(klip["caption_ig"])

print("\nSELESAI! Cek folder 'output_klip/' untuk mengunduh video siap posting + file caption.")
