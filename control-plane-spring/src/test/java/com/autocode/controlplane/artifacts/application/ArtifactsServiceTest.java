/**
 * Unit tests for ArtifactsService - storage and retrieval operations.
 * Validates Requirement 6.4 (comprehensive test coverage for all core services).
 */
package com.autocode.controlplane.artifacts.application;

import com.autocode.controlplane.artifacts.domain.ArtifactContent;
import com.autocode.controlplane.artifacts.domain.ArtifactRecord;
import com.autocode.controlplane.artifacts.ports.ArtifactsPort;
import com.autocode.controlplane.artifacts.ports.AuditPort;
import com.autocode.controlplane.artifacts.ports.DownloadAuthzPort;
import com.autocode.controlplane.artifacts.ports.TaskReadPort;
import com.autocode.controlplane.security.ProjectAuthz;
import com.autocode.controlplane.security.SecurityPrincipalUtils;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.MockedStatic;
import org.mockito.junit.jupiter.MockitoExtension;

import java.io.ByteArrayInputStream;
import java.io.InputStream;
import java.time.Instant;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class ArtifactsServiceTest {

    @Mock
    private ArtifactsPort artifactsPort;

    @Mock
    private DownloadAuthzPort downloadAuthzPort;

    @Mock
    private AuditPort auditPort;

    @Mock
    private TaskReadPort taskReadPort;

    @Mock
    private ProjectAuthz projectAuthz;

    private ArtifactsService artifactsService;

    @BeforeEach
    void setUp() {
        artifactsService = new ArtifactsService(
                artifactsPort,
                downloadAuthzPort,
                auditPort,
                taskReadPort,
                projectAuthz
        );
    }

    // ========== Upload Tests ==========

    @Test
    void upload_ValidTask_StoresArtifactSuccessfully() {
        // Arrange
        String taskId = "tsk_123";
        String name = "output.zip";
        String contentType = "application/zip";
        byte[] data = "test data".getBytes();
        InputStream inputStream = new ByteArrayInputStream(data);

        ArtifactRecord expectedRecord = new ArtifactRecord(
                "art_456",
                taskId,
                name,
                contentType,
                data.length,
                "sha256hash",
                Instant.now()
        );

        when(taskReadPort.exists(taskId)).thenReturn(true);
        when(artifactsPort.store(eq(taskId), eq(name), eq(contentType), any(InputStream.class)))
                .thenReturn(expectedRecord);

        // Act
        ArtifactRecord result = artifactsService.upload(taskId, name, contentType, inputStream);

        // Assert
        assertNotNull(result);
        assertEquals("art_456", result.artifactId());
        assertEquals(taskId, result.taskId());
        assertEquals(name, result.name());
        verify(taskReadPort).exists(taskId);
        verify(artifactsPort).store(eq(taskId), eq(name), eq(contentType), any(InputStream.class));
        verify(auditPort).append(eq(taskId), anyString(), eq("artifact.upload"), any(Map.class));
    }

    @Test
    void upload_NonExistentTask_ThrowsException() {
        // Arrange
        String taskId = "tsk_nonexistent";
        String name = "output.zip";
        String contentType = "application/zip";
        InputStream inputStream = new ByteArrayInputStream("test".getBytes());

        when(taskReadPort.exists(taskId)).thenReturn(false);

        // Act & Assert
        assertThrows(TaskNotFoundException.class, () ->
                artifactsService.upload(taskId, name, contentType, inputStream)
        );
        verify(artifactsPort, never()).store(any(), any(), any(), any());
        verify(auditPort, never()).append(any(), any(), any(), any());
    }

    @Test
    void upload_NullTaskId_ThrowsException() {
        // Arrange
        String name = "output.zip";
        String contentType = "application/zip";
        InputStream inputStream = new ByteArrayInputStream("test".getBytes());

        // Act & Assert
        assertThrows(IllegalArgumentException.class, () ->
                artifactsService.upload(null, name, contentType, inputStream)
        );
        verify(artifactsPort, never()).store(any(), any(), any(), any());
    }

    @Test
    void upload_BlankTaskId_ThrowsException() {
        // Arrange
        String name = "output.zip";
        String contentType = "application/zip";
        InputStream inputStream = new ByteArrayInputStream("test".getBytes());

        // Act & Assert
        assertThrows(IllegalArgumentException.class, () ->
                artifactsService.upload("  ", name, contentType, inputStream)
        );
        verify(artifactsPort, never()).store(any(), any(), any(), any());
    }

    // ========== List Tests ==========

    @Test
    void list_ValidTask_ReturnsArtifacts() {
        // Arrange
        String taskId = "tsk_123";
        List<ArtifactRecord> expectedRecords = List.of(
                new ArtifactRecord("art_1", taskId, "file1.txt", "text/plain", 100, "hash1", Instant.now()),
                new ArtifactRecord("art_2", taskId, "file2.txt", "text/plain", 200, "hash2", Instant.now())
        );

        when(taskReadPort.exists(taskId)).thenReturn(true);
        when(artifactsPort.listByTask(taskId)).thenReturn(expectedRecords);

        // Act
        List<ArtifactRecord> result = artifactsService.list(taskId);

        // Assert
        assertNotNull(result);
        assertEquals(2, result.size());
        assertEquals("art_1", result.get(0).artifactId());
        assertEquals("art_2", result.get(1).artifactId());
        verify(taskReadPort).exists(taskId);
        verify(artifactsPort).listByTask(taskId);
    }

    @Test
    void list_NonExistentTask_ThrowsException() {
        // Arrange
        String taskId = "tsk_nonexistent";
        when(taskReadPort.exists(taskId)).thenReturn(false);

        // Act & Assert
        assertThrows(TaskNotFoundException.class, () ->
                artifactsService.list(taskId)
        );
        verify(artifactsPort, never()).listByTask(any());
    }

    @Test
    void list_EmptyArtifactList_ReturnsEmptyList() {
        // Arrange
        String taskId = "tsk_123";
        when(taskReadPort.exists(taskId)).thenReturn(true);
        when(artifactsPort.listByTask(taskId)).thenReturn(List.of());

        // Act
        List<ArtifactRecord> result = artifactsService.list(taskId);

        // Assert
        assertNotNull(result);
        assertTrue(result.isEmpty());
    }

    // ========== Download Tests ==========

    @Test
    void download_ValidTokenAndArtifact_ReturnsContent() {
        // Arrange
        String taskId = "tsk_123";
        String artifactId = "art_456";
        String token = "valid_token";

        ArtifactRecord record = new ArtifactRecord(
                artifactId, taskId, "file.txt", "text/plain", 100, "hash", Instant.now()
        );
        byte[] data = "file content".getBytes();
        ArtifactContent expectedContent = new ArtifactContent(record, new ByteArrayInputStream(data));

        when(taskReadPort.exists(taskId)).thenReturn(true);
        when(downloadAuthzPort.canDownload(taskId, artifactId, token)).thenReturn(true);
        when(artifactsPort.open(taskId, artifactId)).thenReturn(expectedContent);

        // Act
        ArtifactContent result = artifactsService.download(taskId, artifactId, token);

        // Assert
        assertNotNull(result);
        assertEquals(artifactId, result.record().artifactId());
        verify(downloadAuthzPort).canDownload(taskId, artifactId, token);
        verify(artifactsPort).open(taskId, artifactId);
        verify(auditPort).append(eq(taskId), anyString(), eq("artifact.download"), any(Map.class));
    }

    @Test
    void download_InvalidToken_ThrowsForbiddenException() {
        // Arrange
        String taskId = "tsk_123";
        String artifactId = "art_456";
        String token = "invalid_token";

        when(taskReadPort.exists(taskId)).thenReturn(true);
        when(downloadAuthzPort.canDownload(taskId, artifactId, token)).thenReturn(false);

        // Act & Assert
        assertThrows(ArtifactForbiddenException.class, () ->
                artifactsService.download(taskId, artifactId, token)
        );
        verify(artifactsPort, never()).open(any(), any());
        verify(auditPort, never()).append(any(), any(), any(), any());
    }

    @Test
    void download_NonExistentTask_ThrowsTaskNotFoundException() {
        // Arrange
        String taskId = "tsk_nonexistent";
        String artifactId = "art_456";
        String token = "valid_token";

        when(taskReadPort.exists(taskId)).thenReturn(false);

        // Act & Assert
        assertThrows(TaskNotFoundException.class, () ->
                artifactsService.download(taskId, artifactId, token)
        );
        verify(downloadAuthzPort, never()).canDownload(any(), any(), any());
        verify(artifactsPort, never()).open(any(), any());
    }

    // ========== Preview Tests ==========

    @Test
    void preview_ValidTokenAndArtifact_ReturnsContent() {
        // Arrange
        String taskId = "tsk_123";
        String artifactId = "art_456";
        String token = "valid_token";

        ArtifactRecord record = new ArtifactRecord(
                artifactId, taskId, "file.txt", "text/plain", 100, "hash", Instant.now()
        );
        byte[] data = "file content".getBytes();
        ArtifactContent expectedContent = new ArtifactContent(record, new ByteArrayInputStream(data));

        when(taskReadPort.exists(taskId)).thenReturn(true);
        when(downloadAuthzPort.canDownload(taskId, artifactId, token)).thenReturn(true);
        when(artifactsPort.open(taskId, artifactId)).thenReturn(expectedContent);

        // Act
        ArtifactContent result = artifactsService.preview(taskId, artifactId, token);

        // Assert
        assertNotNull(result);
        assertEquals(artifactId, result.record().artifactId());
        verify(downloadAuthzPort).canDownload(taskId, artifactId, token);
        verify(artifactsPort).open(taskId, artifactId);
        verify(auditPort).append(eq(taskId), anyString(), eq("artifact.preview"), any(Map.class));
    }

    @Test
    void preview_InvalidToken_ThrowsForbiddenException() {
        // Arrange
        String taskId = "tsk_123";
        String artifactId = "art_456";
        String token = "invalid_token";

        when(taskReadPort.exists(taskId)).thenReturn(true);
        when(downloadAuthzPort.canDownload(taskId, artifactId, token)).thenReturn(false);

        // Act & Assert
        assertThrows(ArtifactForbiddenException.class, () ->
                artifactsService.preview(taskId, artifactId, token)
        );
        verify(artifactsPort, never()).open(any(), any());
    }

    // ========== Hosted Site Tests ==========

    @Test
    void openHostedSite_AuthenticatedUserWithAccess_ReturnsContent() {
        // Arrange
        String taskId = "tsk_123";
        String artifactId = "art_456";
        String token = null;

        ArtifactRecord record = new ArtifactRecord(
                artifactId, taskId, "index.html", "text/html", 100, "hash", Instant.now()
        );
        byte[] data = "<html>content</html>".getBytes();
        ArtifactContent expectedContent = new ArtifactContent(record, new ByteArrayInputStream(data));

        when(taskReadPort.exists(taskId)).thenReturn(true);
        when(artifactsPort.open(taskId, artifactId)).thenReturn(expectedContent);

        try (MockedStatic<SecurityPrincipalUtils> mockedStatic = mockStatic(SecurityPrincipalUtils.class)) {
            mockedStatic.when(SecurityPrincipalUtils::currentUsernameOrNull).thenReturn("user123");
            when(projectAuthz.canAccessTask(taskId)).thenReturn(true);

            // Act
            ArtifactContent result = artifactsService.openHostedSite(taskId, artifactId, token);

            // Assert
            assertNotNull(result);
            assertEquals(artifactId, result.record().artifactId());
            verify(projectAuthz).canAccessTask(taskId);
            verify(artifactsPort).open(taskId, artifactId);
        }
    }

    @Test
    void openHostedSite_AuthenticatedUserWithoutAccess_ThrowsNotFoundException() {
        // Arrange
        String taskId = "tsk_123";
        String artifactId = "art_456";
        String token = null;

        when(taskReadPort.exists(taskId)).thenReturn(true);

        try (MockedStatic<SecurityPrincipalUtils> mockedStatic = mockStatic(SecurityPrincipalUtils.class)) {
            mockedStatic.when(SecurityPrincipalUtils::currentUsernameOrNull).thenReturn("user123");
            when(projectAuthz.canAccessTask(taskId)).thenReturn(false);

            // Act & Assert
            assertThrows(ArtifactNotFoundException.class, () ->
                    artifactsService.openHostedSite(taskId, artifactId, token)
            );
            verify(artifactsPort, never()).open(any(), any());
        }
    }

    @Test
    void openHostedSite_AnonymousUserWithValidToken_ReturnsContent() {
        // Arrange
        String taskId = "tsk_123";
        String artifactId = "art_456";
        String token = "valid_token";

        ArtifactRecord record = new ArtifactRecord(
                artifactId, taskId, "index.html", "text/html", 100, "hash", Instant.now()
        );
        byte[] data = "<html>content</html>".getBytes();
        ArtifactContent expectedContent = new ArtifactContent(record, new ByteArrayInputStream(data));

        when(taskReadPort.exists(taskId)).thenReturn(true);
        when(downloadAuthzPort.canDownload(taskId, artifactId, token)).thenReturn(true);
        when(artifactsPort.open(taskId, artifactId)).thenReturn(expectedContent);

        try (MockedStatic<SecurityPrincipalUtils> mockedStatic = mockStatic(SecurityPrincipalUtils.class)) {
            mockedStatic.when(SecurityPrincipalUtils::currentUsernameOrNull).thenReturn(null);

            // Act
            ArtifactContent result = artifactsService.openHostedSite(taskId, artifactId, token);

            // Assert
            assertNotNull(result);
            assertEquals(artifactId, result.record().artifactId());
            verify(downloadAuthzPort).canDownload(taskId, artifactId, token);
            verify(artifactsPort).open(taskId, artifactId);
        }
    }

    @Test
    void openHostedSite_AnonymousUserWithInvalidToken_ThrowsNotFoundException() {
        // Arrange
        String taskId = "tsk_123";
        String artifactId = "art_456";
        String token = "invalid_token";

        when(taskReadPort.exists(taskId)).thenReturn(true);
        when(downloadAuthzPort.canDownload(taskId, artifactId, token)).thenReturn(false);

        try (MockedStatic<SecurityPrincipalUtils> mockedStatic = mockStatic(SecurityPrincipalUtils.class)) {
            mockedStatic.when(SecurityPrincipalUtils::currentUsernameOrNull).thenReturn(null);

            // Act & Assert
            assertThrows(ArtifactNotFoundException.class, () ->
                    artifactsService.openHostedSite(taskId, artifactId, token)
            );
            verify(artifactsPort, never()).open(any(), any());
        }
    }

    @Test
    void openHostedSite_NonExistentTask_ThrowsNotFoundException() {
        // Arrange
        String taskId = "tsk_nonexistent";
        String artifactId = "art_456";
        String token = "valid_token";

        when(taskReadPort.exists(taskId)).thenReturn(false);

        // Act & Assert
        assertThrows(TaskNotFoundException.class, () ->
                artifactsService.openHostedSite(taskId, artifactId, token)
        );
        verify(artifactsPort, never()).open(any(), any());
    }

    // ========== Authorization Assertion Tests ==========

    @Test
    void assertHostedSiteAccess_AuthenticatedUserWithAccess_DoesNotThrow() {
        // Arrange
        String taskId = "tsk_123";
        String artifactId = "art_456";
        String token = null;

        when(taskReadPort.exists(taskId)).thenReturn(true);

        try (MockedStatic<SecurityPrincipalUtils> mockedStatic = mockStatic(SecurityPrincipalUtils.class)) {
            mockedStatic.when(SecurityPrincipalUtils::currentUsernameOrNull).thenReturn("user123");
            when(projectAuthz.canAccessTask(taskId)).thenReturn(true);

            // Act & Assert
            assertDoesNotThrow(() ->
                    artifactsService.assertHostedSiteAccess(taskId, artifactId, token)
            );
            verify(projectAuthz).canAccessTask(taskId);
        }
    }

    @Test
    void assertHostedSiteAccess_AuthenticatedUserWithoutAccess_ThrowsNotFoundException() {
        // Arrange
        String taskId = "tsk_123";
        String artifactId = "art_456";
        String token = null;

        when(taskReadPort.exists(taskId)).thenReturn(true);

        try (MockedStatic<SecurityPrincipalUtils> mockedStatic = mockStatic(SecurityPrincipalUtils.class)) {
            mockedStatic.when(SecurityPrincipalUtils::currentUsernameOrNull).thenReturn("user123");
            when(projectAuthz.canAccessTask(taskId)).thenReturn(false);

            // Act & Assert
            assertThrows(ArtifactNotFoundException.class, () ->
                    artifactsService.assertHostedSiteAccess(taskId, artifactId, token)
            );
        }
    }

    @Test
    void assertHostedSiteAccess_AnonymousUserWithValidToken_DoesNotThrow() {
        // Arrange
        String taskId = "tsk_123";
        String artifactId = "art_456";
        String token = "valid_token";

        when(taskReadPort.exists(taskId)).thenReturn(true);
        when(downloadAuthzPort.canDownload(taskId, artifactId, token)).thenReturn(true);

        try (MockedStatic<SecurityPrincipalUtils> mockedStatic = mockStatic(SecurityPrincipalUtils.class)) {
            mockedStatic.when(SecurityPrincipalUtils::currentUsernameOrNull).thenReturn(null);

            // Act & Assert
            assertDoesNotThrow(() ->
                    artifactsService.assertHostedSiteAccess(taskId, artifactId, token)
            );
            verify(downloadAuthzPort).canDownload(taskId, artifactId, token);
        }
    }

    @Test
    void assertHostedSiteAccess_AnonymousUserWithInvalidToken_ThrowsNotFoundException() {
        // Arrange
        String taskId = "tsk_123";
        String artifactId = "art_456";
        String token = "invalid_token";

        when(taskReadPort.exists(taskId)).thenReturn(true);
        when(downloadAuthzPort.canDownload(taskId, artifactId, token)).thenReturn(false);

        try (MockedStatic<SecurityPrincipalUtils> mockedStatic = mockStatic(SecurityPrincipalUtils.class)) {
            mockedStatic.when(SecurityPrincipalUtils::currentUsernameOrNull).thenReturn(null);

            // Act & Assert
            assertThrows(ArtifactNotFoundException.class, () ->
                    artifactsService.assertHostedSiteAccess(taskId, artifactId, token)
            );
        }
    }
}
