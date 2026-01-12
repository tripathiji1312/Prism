package com.prism.security_core.auth;

import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.*;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.client.RestTemplate;

@RestController
@RequestMapping("/api/video")
@CrossOrigin(origins = "*") // Allows Frontend to talk to Java
public class VideoUploadController {

    @PostMapping("/upload")
    public ResponseEntity<String> uploadVideo(
            @RequestParam("video") MultipartFile file,
            @RequestParam("wallet") String wallet,
            @RequestParam("screenColor") String screenColor) {

        try {
            // Forward the file to Python (Running on the same laptop)
            String pythonUrl = "http://localhost:8000/process-video?wallet=" + wallet;

            RestTemplate restTemplate = new RestTemplate();
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.MULTIPART_FORM_DATA);

            // Convert file to Resource
            ByteArrayResource fileResource = new ByteArrayResource(file.getBytes()) {
                @Override
                public String getFilename() {
                    return "video.webm";
                }
            };

            MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
            body.add("file", fileResource);

            HttpEntity<MultiValueMap<String, Object>> requestEntity = new HttpEntity<>(body, headers);

            // Send to Python
            ResponseEntity<String> response = restTemplate.postForEntity(pythonUrl, requestEntity, String.class);

            return ResponseEntity.ok(response.getBody());

        } catch (Exception e) {
            e.printStackTrace();
            return ResponseEntity.status(500).body("Error processing video: " + e.getMessage());
        }
    }
}