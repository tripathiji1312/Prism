package com.prism.security_core.service;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Base64;
import java.util.Comparator;
import java.util.stream.Stream;

import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.client.RestTemplate;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;

@Service
public class VideoProcessingService {

    // Folders to store data
    private static final String UPLOAD_DIR = "Video/";
    private static final String FRAMES_DIR = "Video/frames/";
    private static final String JSON_DIR = "Video/json/";
    
    // Python Backend URL (Port 8000)
    private static final String PYTHON_ENDPOINT = "http://localhost:8000/process-file";
    
    // Local Blockchain Endpoint (Port 8080 - Self Call)
    private static final String BLOCKCHAIN_ENDPOINT = "http://localhost:8080/api/verify/human?force=true";

    public String processVideo(MultipartFile file, String wallet, String screenColor) throws Exception {
        // 1. Create Directories
        new File(UPLOAD_DIR).mkdirs();
        new File(FRAMES_DIR).mkdirs();
        new File(JSON_DIR).mkdirs();

        // 2. Save Video
        String cleanName = file.getOriginalFilename().replaceAll("[^a-zA-Z0-9.-]", "_");
        String fileName = System.currentTimeMillis() + "_" + cleanName;
        Path videoPath = Paths.get(UPLOAD_DIR + fileName);
        Files.write(videoPath, file.getBytes());

        // 3. Extract Frames
        String framePattern = FRAMES_DIR + "frame_%03d.jpg";
        
        // TODO: Ensure this path is correct for your system!
        String ffmpegPath = "ffmpeg"; // Or "C:\\ffmpeg\\bin\\ffmpeg.exe" on Windows

        ProcessBuilder pb = new ProcessBuilder(
                ffmpegPath,
                "-i", videoPath.toString(),
                "-vf", "scale=640:-1",
                "-r", "5", 
                "-q:v", "2", 
                framePattern);

        pb.redirectErrorStream(true);
        Process process = pb.start();
        process.waitFor(); 

        // 4. Generate JSON
        String jsonFilePath = generateJsonFromFrames(wallet, screenColor, fileName);
        
        // 5. Chain: Call Python -> Get Score -> Call Blockchain
        return notifyPython(jsonFilePath);
    }

    private String generateJsonFromFrames(String wallet, String screenColor, String videoName) throws Exception {
        ObjectMapper mapper = new ObjectMapper();
        ArrayNode framesArray = mapper.createArrayNode();

        try (Stream<Path> paths = Files.walk(Paths.get(FRAMES_DIR))) {
            paths.filter(Files::isRegularFile)
                    .filter(p -> p.toString().endsWith(".jpg"))
                    .sorted(Comparator.comparing(Path::toString))
                    .forEach(path -> {
                        try {
                            byte[] fileContent = Files.readAllBytes(path);
                            String base64 = Base64.getEncoder().encodeToString(fileContent);

                            ObjectNode frameNode = mapper.createObjectNode();
                            frameNode.put("image", base64);
                            frameNode.put("screenColor", screenColor);
                            frameNode.put("wallet", wallet);

                            framesArray.add(frameNode);
                            Files.delete(path); // Cleanup frame
                        } catch (IOException e) {
                            e.printStackTrace();
                        }
                    });
        }

        String jsonFileName = JSON_DIR + videoName + "_data.json";
        mapper.writeValue(new File(jsonFileName), framesArray);
        return jsonFileName;
    }

    private String notifyPython(String jsonFilePath) {
        System.out.println("🔗 1. Calling Python Analysis...");
        File f = new File(jsonFilePath);
        System.out.println("   File Path: " + f.getAbsolutePath());
        
        try {
            RestTemplate restTemplate = new RestTemplate();
            ObjectMapper mapper = new ObjectMapper();
            
            // A. Send Path to Python
            ObjectNode payload = mapper.createObjectNode();
            payload.put("json_path", jsonFilePath);

            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            HttpEntity<String> request = new HttpEntity<>(payload.toString(), headers);

            String pythonResponseStr = restTemplate.postForObject(PYTHON_ENDPOINT, request, String.class);
            System.out.println("✅ Python Analysis Complete: " + pythonResponseStr);

            // B. Check if Verified
            JsonNode pythonResponse = mapper.readTree(pythonResponseStr);
            String status = pythonResponse.has("status") ? pythonResponse.get("status").asText() : "failed";

            if ("verified".equalsIgnoreCase(status)) {
                System.out.println("🔗 2. Triggering Blockchain Minting...");
                
                HttpHeaders verifyHeaders = new HttpHeaders();
                verifyHeaders.setContentType(MediaType.APPLICATION_JSON);
                verifyHeaders.set("X-API-KEY", "prism-python-secret"); 

                // Pass the Python scores to the Blockchain Controller
                HttpEntity<String> verifyRequest = new HttpEntity<>(pythonResponseStr, verifyHeaders);
                
                String blockchainResponse = restTemplate.postForObject(BLOCKCHAIN_ENDPOINT, verifyRequest, String.class);
                System.out.println("🎉 Blockchain Success: " + blockchainResponse);
                
                return blockchainResponse;
            } else {
                return pythonResponseStr; // Return failure reason
            }

        } catch (Exception e) {
            e.printStackTrace();
            return "{\"status\": \"error\", \"message\": \"Pipeline Error: " + e.getMessage() + "\"}";
        }
    }
}